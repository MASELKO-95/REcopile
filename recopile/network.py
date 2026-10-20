from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

USER_AGENT = "Recopile-Games-Hub/0.1.0"
MAX_DOWNLOAD = 2 * 1024**3
MAX_EXTRACT = 10 * 1024**3
ALLOWED_HOSTS = {"api.github.com", "github.com", "raw.githubusercontent.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com", "github-releases.githubusercontent.com"}


class UserError(Exception):
    pass


class Cancelled(UserError):
    pass


def validate_repo(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.startswith("https://github.com/"):
        value = value[len("https://github.com/"):]
    value = value.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
        raise UserError("Podaj repozytorium jako właściciel/projekt albo pełny adres https://github.com/właściciel/projekt.")
    return value


def validate_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise UserError("Adres pobierania musi prowadzić do GitHuba przez HTTPS.")


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url: str, timeout=35):
    validate_url(url)
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json" if "api.github.com/" in url else "*/*"})
    try:
        return build_opener(SafeRedirect()).open(req, timeout=timeout)
    except HTTPError as exc:
        if exc.code == 404:
            raise UserError("Nie znaleziono repozytorium lub wydania w GitHub Releases.") from exc
        if exc.code in (403, 429):
            raise UserError("GitHub ograniczył zapytania. Spróbuj ponownie po odnowieniu limitu API.") from exc
        raise UserError(f"GitHub zwrócił błąd HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise UserError("Nie udało się połączyć z GitHubem. Sprawdź internet i spróbuj ponownie.") from exc


def fetch_json(url: str):
    with open_url(url) as response:
        raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise UserError("Odpowiedź GitHuba jest zbyt duża.")
        return json.loads(raw)


def latest_release(source: dict):
    repo = validate_repo(source["repo"])
    tag = source.get("release_tag")
    endpoint = "/releases/tags/" + quote(tag, safe="") if tag else "/releases/latest"
    release = fetch_json("https://api.github.com/repos/" + repo + endpoint)
    if release.get("draft") or release.get("prerelease"):
        raise UserError("To wydanie nie jest stabilne.")
    assets = [a for a in release.get("assets", []) if fnmatch.fnmatchcase(a.get("name", ""), source.get("asset_pattern", "")) and
              not (source.get("exclude_pattern") and fnmatch.fnmatchcase(a["name"], source["exclude_pattern"]))]
    if len(assets) != 1:
        message = "Brak pasującej paczki dla tego urządzenia" if not assets else "Kilka paczek pasuje do wzorca — doprecyzuj źródło"
        raise UserError(message + f" ({source.get('asset_pattern', 'brak wzorca')}).")
    asset = assets[0]
    validate_url(asset["browser_download_url"])
    return {"version": release["tag_name"], "url": release["html_url"], "published_at": release.get("published_at"),
            "notes": release.get("body", "")[:16000], "asset": asset, "assets": release.get("assets", [])}


def expected_checksum(release: dict):
    asset = release["asset"]
    digest = asset.get("digest", "") or ""
    if re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        return digest[7:].lower()
    for other in release.get("assets", []):
        if other["name"] == asset["name"] + ".sha256" and other.get("size", 0) <= 1024:
            with open_url(other["browser_download_url"]) as response:
                match = re.fullmatch(r"\s*([a-fA-F0-9]{64})(?:\s+\*?[^\r\n]+)?\s*", response.read(1025).decode("ascii", errors="replace"))
            if match: return match[1].lower()
    for other in release.get("assets", []):
        if other["name"].lower() in {"sha256sums", "sha256sums.txt", "checksums.txt", "sha256sum.txt"} and other.get("size", 0) < 1_000_000:
            with open_url(other["browser_download_url"]) as response:
                text = response.read(1_000_000).decode("utf-8", errors="replace")
            for line in text.splitlines():
                match = re.match(r"^([a-fA-F0-9]{64})\s+\*?(.+)$", line)
                if match and match[2].removeprefix("./") == asset["name"]:
                    return match[1].lower()
    # Some projects publish checksums in the release body rather than assets.
    for line in release.get("notes", "").splitlines():
        if asset["name"] in line:
            match = re.search(r"\b[a-fA-F0-9]{64}\b", line)
            if match:
                return match[0].lower()
    return None


def download(asset: dict, destination: Path, progress, cancelled, checksum=None):
    size = int(asset.get("size", 0))
    if not 0 < size <= MAX_DOWNLOAD:
        raise UserError("Niepoprawny rozmiar paczki (limit 2 GB).")
    digest = hashlib.sha256()
    read = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open_url(asset["browser_download_url"]) as response, destination.open("xb") as output:
            while True:
                if cancelled():
                    raise Cancelled("Anulowano pobieranie.")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                read += len(chunk)
                if read > size or read > MAX_DOWNLOAD:
                    raise UserError("Rozmiar pobranej paczki nie zgadza się z wydaniem.")
                output.write(chunk)
                digest.update(chunk)
                progress(read, size)
        if read != size:
            raise UserError("Pobieranie jest niekompletne. Uruchom instalację ponownie.")
        actual = digest.hexdigest()
        if checksum and actual != checksum.lower():
            raise UserError("Suma SHA-256 jest niezgodna. Instalacja została zatrzymana.")
        return actual
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def safe_member(name: str, destination: Path) -> Path:
    if "\\" in name or "\x00" in name or ":" in name:
        raise UserError("Paczka zawiera niebezpieczną nazwę pliku.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise UserError("Paczka próbuje zapisać pliki poza folderem instalacji.")
    target = destination.joinpath(*path.parts)
    if not target.resolve().is_relative_to(destination.resolve()):
        raise UserError("Niepoprawna ścieżka w paczce.")
    return target


def extract(archive: Path, destination: Path, original_name: str):
    destination.mkdir(parents=True, exist_ok=False)
    total = 0
    if original_name.lower().endswith(".appimage"):
        shutil.copy2(archive, destination / original_name)
        (destination / original_name).chmod(0o755)
        return
    if original_name.lower().endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            entries = z.infolist()
            if len(entries) > 100000:
                raise UserError("Paczka zawiera zbyt wiele plików.")
            for member in entries:
                path = safe_member(member.filename, destination)
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise UserError("Dowiązania w paczkach ZIP nie są obsługiwane.")
                total += member.file_size
                if total > MAX_EXTRACT:
                    raise UserError("Paczka po rozpakowaniu przekracza limit 10 GB.")
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, path.open("xb") as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                    path.chmod(0o755 if mode & 0o111 else 0o644)
        return
    if original_name.lower().endswith(".7z"):
        try: import py7zr
        except ImportError: raise UserError("Ten pakiet wymaga obsługi 7z. Użyj instalatora Recopile z dołączoną biblioteką py7zr.")
        with py7zr.SevenZipFile(archive, mode="r") as z:
            if z.needs_password() or len(z.files) > 100000: raise UserError("Paczka 7z jest zaszyfrowana lub zawiera zbyt wiele plików.")
            names = set()
            for member in z.files:
                safe_member(member.filename, destination)
                if member.filename.casefold() in names: raise UserError("Paczka ma kolidujące nazwy plików.")
                names.add(member.filename.casefold())
                if not member.is_directory and not member.is_file: raise UserError("Dowiązania i pliki specjalne w 7z nie są obsługiwane.")
                total += member.uncompressed or 0
                if total > MAX_EXTRACT: raise UserError("Paczka po rozpakowaniu przekracza limit 10 GB.")
            z.extractall(path=destination)
            for path in destination.rglob("*"):
                if path.is_symlink() or not path.resolve().is_relative_to(destination.resolve()): raise UserError("Niebezpieczny plik po rozpakowaniu 7z.")
        return
    if original_name.lower().endswith((".tar.gz", ".tgz", ".tar.xz", ".tar")):
        with tarfile.open(archive) as tar:
            entries = tar.getmembers()
            if len(entries) > 100000:
                raise UserError("Paczka zawiera zbyt wiele plików.")
            links = []
            for member in entries:
                path = safe_member(member.name, destination)
                total += member.size
                if total > MAX_EXTRACT:
                    raise UserError("Paczka po rozpakowaniu przekracza limit 10 GB.")
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as src, path.open("xb") as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                    path.chmod(0o755 if member.mode & 0o111 else 0o644)
                elif member.issym() or member.islnk():
                    # Validate again after ordinary files are extracted. Never follow an
                    # archive symlink while writing later entries.
                    links.append((member, path))
                else:
                    raise UserError("Paczka zawiera plik specjalny lub urządzenie.")
            for member, path in links:
                if path.exists() or path.is_symlink():
                    raise UserError("Paczka zawiera kolidujące dowiązanie.")
                target = safe_member(member.linkname, destination) if member.islnk() else (path.parent / member.linkname).resolve()
                if not target.resolve().is_relative_to(destination.resolve()) or not target.exists():
                    raise UserError("Dowiązanie w paczce prowadzi poza instalację lub do brakującego pliku.")
                path.parent.mkdir(parents=True, exist_ok=True)
                if member.islnk():
                    os.link(target, path)
                else:
                    path.symlink_to(os.path.relpath(target, path.parent))
        return
    raise UserError("Obsługiwane paczki: ZIP, 7z, TAR.GZ, TAR.XZ i AppImage.")
