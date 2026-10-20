from __future__ import annotations

import hashlib
import base64
import json
import os
import platform as host_platform
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from . import __version__
from .jobs import Jobs
from .library import location, point_current, write_manifest
from .network import Cancelled, UserError, download, expected_checksum, extract, fetch_json, latest_release, validate_repo, version_key
from .storage import Store, game_id
from .registry import FIELDS, entry, validate_registry
from .profiles import Profiles
from .compatibility import Compatibility, validate_reports
from .legal import ProjectDocuments
from . import development, runners
from .mods import Workshop
from .media import GameMedia
from .platforms import PLATFORMS, device_options
from .port_setup import PortSetup
from .steam import SteamLibrary
from .performance import Performance
from .game_settings import GameSettings


class Launcher:
    def __init__(self, app_root: Path, state_root: Path, automatic=True, *, scan_steam=None):
        self.app_root = app_root
        self.store = Store(app_root, state_root)
        self.jobs = Jobs(self.store)
        self.profiles = Profiles(self.store)
        self.compatibility = Compatibility(self.store)
        self.documents = ProjectDocuments(self.store)
        self.workshop = Workshop(self)
        self.media = GameMedia(self.store)
        self.port_setup = PortSetup(self)
        self.game_settings = GameSettings(self)
        self.running = {}
        self.process_lock = threading.RLock()
        self.stop = threading.Event()
        self.performance = Performance(self)
        self.steam = SteamLibrary(self)
        should_scan_steam = automatic if scan_steam is None else scan_steam
        if should_scan_steam and self.steam.enabled():
            self.steam.scan()
        if automatic:
            threading.Thread(target=self._update_loop, daemon=True, name="recopile-updates").start()

    def bootstrap(self):
        prefs = self.preferences()
        return {"version": __version__, "media_revision": self.media.revision, "stats": self.store.stats(), "settings": prefs,
                "sources": self.store.list("sources"), "engines": self.engines(), "jobs": self.jobs.list(),
                "catalog": self.store.get("settings", "catalog"), "running": self.active_processes(),
                "catalog_sync":self.store.get('settings','catalog_sync'),
                "host": self.compatibility.device, "runners":runners.discover(prefs) if self.system_key()=='linux' else {"proton":[],"wine":None,"umu":None},
                "collections":self.collections(), "profiles": self.store.list("profiles"), "profile": self.profiles.summary(),
                "pending_updates": self.store.get("settings", "pending_updates", []), "app_notice":self.documents.app_notice(__version__),
                "last_update_check": self.store.get("settings", "last_update_check"),
                "launcher_update": self.store.get("settings", "launcher_update"), "libraries": self.libraries(), "steam":self.steam.state()}

    def preferences(self):
        return self.store.get("settings", "preferences")

    def save_preferences(self, changes):
        allowed = {"only_recompiled", "check_updates", "auto_update", "games_dir", "bios_path", "xenia_path", "launcher_repo", "profile_name", "update_interval_hours", "discord_url", "android_ads", "proton_path", "umu_path", "language"}
        prefs = self.preferences()
        for name, value in changes.items():
            if name not in allowed:
                continue
            if name=='language' and value not in {'pl','en','hu'}: raise UserError('Wybierz język: polski, angielski lub węgierski.')
            if name in {"only_recompiled", "check_updates", "auto_update", "android_ads"} and not isinstance(value, bool):
                raise UserError("Niepoprawna wartość ustawienia.")
            if name == "android_ads" and self.system_key() != "android":
                value = False
            if name == "update_interval_hours" and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 168):
                raise UserError("Interwał aktualizacji musi wynosić od 1 do 168 godzin.")
            if name in {"games_dir", "bios_path", "xenia_path", "proton_path", "umu_path"}:
                if not isinstance(value, str) or len(value) > 4096:
                    raise UserError("Niepoprawna ścieżka.")
                if value:
                    value = str(Path(value).expanduser().resolve())
                    if name != "games_dir" and not Path(value).is_file():
                        raise UserError("Wskazany plik nie istnieje.")
            if name == "games_dir":
                if not value:
                    raise UserError("Podaj folder instalacji.")
                folder = Path(value)
                folder.mkdir(parents=True, exist_ok=True)
                if not os.access(folder, os.W_OK):
                    raise UserError("Brak prawa zapisu do folderu instalacji.")
                prefs["libraries"] = list(dict.fromkeys([*prefs.get("libraries", [prefs["games_dir"]]), str(folder)]))
            if name == "launcher_repo":
                value = validate_repo(value) if value.strip() else ""
            if name == "discord_url" and value and not re.fullmatch(r"https://(?:discord\.gg/|discord\.com/invite/)[A-Za-z0-9_-]+", value):
                raise UserError("Podaj link zaproszenia https://discord.gg/... lub https://discord.com/invite/...")
            if name == "profile_name":
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= 40:
                    raise UserError("Nazwa profilu musi mieć od 1 do 40 znaków.")
                value = value.strip()
                self.profiles.rename(value)
            prefs[name] = value
        return self.store.put("settings", "preferences", prefs)

    def finish_notice(self, data):
        prefs = self.preferences()
        if self.documents.app_notice(__version__)["required"] and data.get("accepted") is not True:
            raise UserError("Zapoznaj się z licencją i informacją o prywatności.")
        if self.system_key() == "android" and not prefs.get("onboarding_complete") and not isinstance(data.get("android_ads"), bool):
            raise UserError("Wybierz, czy chcesz wspierać autora reklamami.")
        self.store.put("settings", "preferences", {**prefs, "onboarding_complete":True, "last_notice_version":__version__,
            "accepted_app_license":self.documents.app_notice(__version__)["license_hash"],
            "app_license_accepted":data.get('accepted') is True or prefs.get('app_license_accepted') is True,
            "android_ads":bool(data.get("android_ads", prefs.get("android_ads"))) if self.system_key() == "android" else False})
        self.apply_pending_updates()
        return {"ok":True}

    def local_project_information(self,source): return development.information(self.store,source)

    def collections(self):
        path=self.app_root/'data/collections.json'
        collections=json.loads(path.read_text())['collections'] if path.is_file() else []
        for collection in collections:
            for item in collection.get('entries',[]):
                game=self.store.game(game_id(item['platform'],item['match']))
                item['game']=self.store.decorate(game) if game else None
                if item['game']: self.describe_game(item['game'])
                if item['game'] and item.get('wiki_title'):
                    item['game']['wiki_title']=item['wiki_title']
            collection['cover_game']=next((item['game'] for item in collection.get('entries',[]) if item['game']),None)
            for item in collection.get('pc_titles',[]):
                game=self.store.game(game_id('other',item['title']))
                item['game']=self.store.decorate(game) if game else None
                if item['game']: self.describe_game(item['game'])
        return collections

    def bind_project(self,data):
        if data.get('source_id')!='ratchet3-local' or data.get('trusted') is not True: raise UserError('Potwierdź lokalny projekt Ratcheta.')
        return development.bind_ratchet(self,data.get('root',''),game_id('ps2','Ratchet & Clank 3'))

    def update_source(self, source_id, data):
        old = self.source(source_id)
        fields = {"repo", "name", "assets_by_system", "executables_by_system", "asset_pattern", "executable", "mod_root"}
        candidate = {**old, **{k:v for k,v in data.items() if k in fields}}
        repo = validate_repo(candidate.get("repo", "")) if candidate.get("repo") else ''
        if not repo and old.get('origin')!='development': raise UserError('Podaj repozytorium GitHub.')
        candidate["repo"] = repo
        if old.get("origin") == "development" and repo and any(candidate.get("assets_by_system", {}).values()):
            candidate.pop("origin",None)
        validate_registry({"schema_version":1,"sources":[{k:v for k,v in candidate.items() if k in FIELDS}],"featured":[]})
        if data.get("trusted") is not True: raise UserError("Potwierdź zaufanie do źródła i przejrzyj dokumentację przed pobraniem.")
        changed = any(candidate.get(k) != old.get(k) for k in fields)
        if changed:
            candidate.update({"verified":False,"user_override":True,"trusted":True,"checked_at":0,"last_error":None,
                              "note":"Źródło zmienione lokalnie przez użytkownika. Przed pobraniem zapoznaj się z jego README i licencją."})
            candidate.pop("release",None)
            candidate.pop("documentation_repo",None)
            candidate.pop("documentation_ref",None)
            if old.get("repo") != repo: candidate.pop("repos_by_system",None)
        return self.store.put("sources",source_id,candidate)

    def project_information(self, source_id):
        if source_id == "launcher":
            source = self.launcher_source()
            return self.documents.get(source, latest_release(source))
        source = self.source(source_id)
        if source.get("origin") == "development" and not source.get("repo"): return self.local_project_information(source)
        try:
            target = self.target_source(source)
            release = self.release(source)
        except UserError:
            metadata = fetch_json("https://api.github.com/repos/" + validate_repo(source["repo"]))
            ref = fetch_json("https://api.github.com/repos/" + source["repo"] + "/commits/" + metadata["default_branch"])["sha"]
            target = source
            release = {"version":ref,"url":"https://github.com/"+source["repo"]+"/tree/"+ref,"asset":{"name":"Kod źródłowy · brak gotowej paczki","size":0},"notes":source.get("note", "") + "\n\nInstrukcja kompilacji pochodzi z README autora. Nie uruchamiamy kodu źródłowego automatycznie."}
        return self.documents.get(target, release)

    def launcher_source(self):
        repo = self.preferences().get("launcher_repo", "")
        if not repo: raise UserError("Wydawca nie skonfigurował jeszcze repozytorium launchera.")
        patterns = {"linux":"Recopile-*-linux-x86_64.AppImage", "windows":"Recopile-*-windows-x64-Setup.exe", "android":"Recopile-*-android.apk"}
        return {"id":"launcher", "name":"Recopile Games Hub", "repo":validate_repo(repo), "asset_pattern":patterns[self.system_key()],
                "scan_releases":True, "allow_prerelease":'-' in __version__}

    def check_launcher_release(self):
        source = self.launcher_source()
        release = latest_release(source)
        version = release["version"].lstrip("v")
        if version_key(version) <= version_key(__version__):
            self.store.put("settings","launcher_update", {"available":False,"version":__version__})
            return {"available":False,"version":__version__}
        documents = self.documents.get(source, release)
        marker = {"available":True,"version":release["version"],"ready":False,"url":release["url"],"documents":documents,
            "permitted":self.documents.permitted(documents,automatic=True)}
        self.store.put("settings","launcher_update",marker)
        return marker

    def libraries(self):
        installs = self.store.list("installs")
        result = []
        for path in self.preferences().get("libraries", [self.preferences()["games_dir"]]):
            probe = Path(path)
            while not probe.exists():
                probe = probe.parent
            usage = shutil.disk_usage(probe)
            result.append({"path": path, "default": path == self.preferences()["games_dir"], "free": usage.free, "total": usage.total,
                           "installed": sum(i.get("library_root") == path and not i["id"].startswith("engine-") for i in installs)})
        return result

    def save_install(self, ident, install):
        Path(install["game_root"]).mkdir(parents=True, exist_ok=True)
        if install.get("user_root"):
            Path(install["user_root"]).mkdir(parents=True, exist_ok=True)
        write_manifest(install)
        point_current(install)
        return self.store.put("installs", ident, install)

    def game_location(self, ident, title, platform, old=None):
        return {**location(Path(self.preferences()["games_dir"]), ident, title, platform), **(old or {})}

    def require_game(self, ident):
        game = self.store.game(ident)
        if not game:
            raise UserError("Nie znaleziono gry.")
        return game

    def detail(self, ident):
        game = self.require_game(ident)
        result = self.store.decorate(game)
        result["variants"] = game.get("variants", [])[:120]
        result["engine"] = next((e for e in self.engines() if e["platform"] == game["platform"]), None)
        self.describe_game(result)
        return result

    def describe_game(self, game):
        game["port_setup"] = self.port_setup.information(game)
        game["game_settings"] = self.game_settings.information(game)
        if any(s['id']=='ratchet3-local' for s in game.get('sources',[])):
            game['local_project']=self.store.get('settings','project:ratchet3-local',{})
        if (game["port_setup"] and game.get("install")
                and game["install"].get("source_id") == game["port_setup"]["source_id"]
                and not game["install"].get("local_executable")):
            game["install"] = {**game["install"], "ready": game["port_setup"]["ready"]}
        game["compatibility"] = self.compatibility.describe(game)
        game["device_options"] = device_options(game, self.system_key())
        return game

    def query(self, **params):
        if params.pop("device_only", False) or params.get("view") == "device":
            params["eligible_ids"] = [g["id"] for g in self.store.device_candidates() if device_options(g, self.system_key())]
        result = self.store.query(**params)
        for game in result["games"]:
            self.describe_game(game)
        return result

    def request_media(self, data):
        ids = data.get("game_ids")
        covers = data.get("covers", False)
        if not isinstance(ids, list) or not 1 <= len(ids) <= 12 or any(not isinstance(i, str) for i in ids) or not isinstance(covers, bool):
            raise UserError("Wybierz od 1 do 12 widocznych gier.")
        games = [self.require_game(ident) for ident in dict.fromkeys(ids)]
        # Collection representatives can disambiguate the first game's article
        # without changing installed/catalog identities or requesting the series.
        representatives={c['cover_game']['id']:c['cover_game'] for c in self.collections() if c.get('cover_game')}
        games=[{**game, 'wiki_title':representatives[game['id']]['wiki_title']}
               if representatives.get(game['id'],{}).get('wiki_title') else game for game in games]
        return self.media.request(games, covers=covers)

    def add_library(self, ident, added=True):
        game = self.require_game(ident)
        game["added"] = bool(added)
        self.store.save_game(game)
        return self.store.decorate(game)

    def add_source(self, data):
        if data.get("publish_catalog"):
            raise UserError("Launcher zapisuje źródła wyłącznie w lokalnej bibliotece.")
        if not data.get("trusted"):
            raise UserError("Potwierdź, że ufasz podanemu repozytorium. Launcher będzie pobierał z niego programy.")
        repo = validate_repo(data.get("repo", ""))
        name = str(data.get("name", "")).strip()
        title = str(data.get("title", "")).strip()
        platform = data.get("platform", "other")
        kind = data.get("kind", "native")
        if not name or len(name) > 100 or not title or len(title) > 200:
            raise UserError("Podaj nazwę źródła i tytuł gry.")
        if platform not in PLATFORMS or kind not in {"native", "recompile"}:
            raise UserError("Niepoprawna platforma lub rodzaj portu.")
        pattern = str(data.get("asset_pattern", "")).strip()
        if not pattern or len(pattern) > 200 or "/" in pattern or "\\" in pattern:
            raise UserError("Podaj wzorzec nazwy paczki Linux, np. *Linux*.tar.gz.")
        executable = str(data.get("executable", "")).strip()
        if executable and (Path(executable).is_absolute() or ".." in Path(executable).parts or "\\" in executable):
            raise UserError("Plik startowy musi być ścieżką względną wewnątrz paczki.")
        ident = "user-" + uuid.uuid4().hex[:12]
        source = {"id": ident, "name": name, "repo": repo, "platform": platform, "kind": kind,
                  "asset_pattern": pattern, "executable": executable, "adapter": "native", "verified": False,
                  "trusted": True, "guide": "https://github.com/" + repo, "note": "Źródło dodane przez użytkownika. Status rekompilacji jest deklaracją autora wpisu.", "created_at": time.time()}
        game_ident = data.get("game_id") or game_id(platform, title)
        game = self.store.game(game_ident) or {"id": game_ident, "title": title, "platform": platform, "variants": []}
        if game["platform"] != platform:
            raise UserError("Platforma źródła musi odpowiadać grze.")
        source["game_id"] = game_ident
        source["game_title"] = game["title"]
        source["assets_by_system"] = data.get("assets_by_system") or {self.system_key(): pattern}
        source["executables_by_system"] = data.get("executables_by_system") or {self.system_key(): executable}
        validate_registry(entry(source, game))
        self.store.put("sources", ident, source)
        game["source_ids"] = [*game.get("source_ids", []), ident]
        game["kind"] = kind
        game["added"] = True
        self.store.save_game(game)
        return {"source": source, "game": self.store.decorate(game)}

    @staticmethod
    def system_key():
        return "android" if os.environ.get("RECOPILE_ANDROID") else {"Linux":"linux", "Windows":"windows"}.get(host_platform.system(), "unknown")

    def target_source(self, source):
        if source.get("origin") == "development":
            raise UserError("Projekt jest w trakcie prac. Użyj dokumentacji lub podłącz dostępny lokalny eksperyment; gotowej paczki do pobrania jeszcze nie ma.")
        key = self.system_key()
        patterns = source.get("assets_by_system", {"linux": source.get("asset_pattern")})
        pattern = patterns.get(key)
        if not pattern:
            raise UserError("To źródło nie publikuje gotowej paczki dla " + self.compatibility.device["system"] + ". Sprawdź instrukcję projektu.")
        target = {**source, "asset_pattern": pattern, "executable": source.get("executables_by_system", {}).get(key, source.get("executable", "")),
                  "repo": source.get("repos_by_system", {}).get(key, source["repo"])}
        tag = source.get("release_tags_by_system", {}).get(key)
        if tag: target["release_tag"] = tag
        else: target.pop("release_tag", None)
        if key == "windows" and target.get("adapter") in {"appimage", "flatpak"}: target["adapter"] = "native"
        if key == "android": target["adapter"] = "apk"
        return target

    def sync_catalog(self):
        repo = self.preferences().get("launcher_repo", "")
        if not repo: return {"message": "Katalog działa lokalnie. Ustaw repozytorium wydawcy po publikacji."}
        repo = validate_repo(repo)
        payload = fetch_json("https://api.github.com/repos/" + repo + "/contents/data/registry.json")
        if payload.get("encoding") != "base64" or payload.get("size", 0) > 2_000_000:
            raise UserError("Niepoprawny katalog wydawcy.")
        registry = validate_registry(json.loads(base64.b64decode(payload["content"])))
        for source in registry["sources"]:
            old = self.store.get("sources", source["id"], {})
            if old.get("user_override"): continue
            changed = old and any(old.get(k) != source.get(k) for k in ["repo", "asset_pattern", "executable", "assets_by_system"])
            merged = {**old, **source, "trusted": old.get("trusted", bool(source.get("verified"))), "catalog_repo": repo}
            if changed:
                merged.pop("release", None)
                merged["checked_at"] = 0
            self.store.put("sources", source["id"], merged)
        for featured in registry["featured"]:
            ident = game_id(featured["platform"], featured.get("match", featured["title"]))
            game = self.store.game(ident) or {"id":ident, "title":featured["title"], "platform":featured["platform"], "variants":[]}
            sources = list(dict.fromkeys([*featured.get("source_ids", []), *game.get("source_ids", [])]))
            kinds = [self.source(s)["kind"] for s in sources]
            kind = "recompile" if "recompile" in kinds else "native" if "native" in kinds else "emulation"
            self.store.save_game({**game, **{k:v for k,v in featured.items() if k not in {"match", "source_ids"}}, "source_ids":sources, "kind":kind, 'catalog_repo':repo})
        try:
            reports = fetch_json("https://raw.githubusercontent.com/" + repo + "/HEAD/data/compatibility.json")
            self.store.put("settings", "public_compatibility", validate_reports(reports))
        except UserError: pass
        result = {"time":time.time(), "repo":repo, "sha":payload.get("sha"), "sources":len(registry["sources"]), "entries":len(registry["featured"]),
                  'catalog_version':registry.get('catalog_version'),'notes':registry.get('catalog_notes','')}
        self.store.put("settings", "catalog_sync", result)
        return result

    def inspect_source(self, repo):
        repo = validate_repo(repo)
        metadata = fetch_json("https://api.github.com/repos/" + repo)
        try:
            release = fetch_json("https://api.github.com/repos/" + repo + "/releases/latest")
            return {"repo": repo, "name": metadata["name"], "archived": metadata.get("archived", False),
                    "version": release["tag_name"], "assets": [{"name": a["name"], "size": a["size"]} for a in release.get("assets", [])]}
        except UserError:
            return {"repo": repo, "name": metadata["name"], "archived": metadata.get("archived", False), "assets": [],
                    "message": "Repozytorium istnieje, ale nie udało się pobrać stabilnego wydania. Wpisz wzorzec paczki ręcznie albo podłącz własną kompilację."}

    def add_local_game(self, data):
        title = str(data.get("title", "")).strip()
        if not title or len(title) > 200:
            raise UserError("Podaj tytuł gry (do 200 znaków).")
        platform = data.get("platform", "other")
        if platform not in PLATFORMS:
            raise UserError("Niepoprawna platforma.")
        # Validate before adding a catalog entry; failed forms leave no partial game.
        path = Path(str(data.get("path", ""))).expanduser().resolve()
        if not data.get("trusted") or not path.is_file() or not os.access(path, os.R_OK):
            raise UserError("Wskaż istniejący plik startowy i potwierdź, że mu ufasz.")
        ident = game_id(platform, title)
        existing = self.store.game(ident)
        game = existing or {"id": ident, "title": title, "platform": platform, "kind": "native", "variants": []}
        self.store.save_game({**game, "added": True,"kind":game['kind'] if game.get('kind')=='recompile' else 'native','external_local':True})
        return self.register_executable(ident, data)

    def mark_ready(self, ident):
        game = self.require_game(ident)
        install = self.store.get("installs", ident)
        if not install or not install.get("setup_started_at"):
            raise UserError("Najpierw uruchom konfigurację portu i ukończ ją w oknie projektu.")
        if game["kind"] not in {"recompile", "native"}:
            raise UserError("Ten typ gry nie wymaga konfiguracji portu.")
        with self.process_lock:
            if ident in self.running:
                raise UserError("Zamknij konfigurator, zanim potwierdzisz gotowość.")
        return self.save_install(ident, {**install, "ready": True, "ready_confirmed_by_user": True})

    def engines(self):
        sources = self.store.list("sources")
        result = []
        for ident, label, platform in [("pcsx2", "PCSX2", "ps2"), ("rpcs3", "RPCS3", "ps3")]:
            installed = self.store.get("installs", "engine-" + ident)
            result.append({"id": ident, "name": label, "platform": platform, "source": next((s for s in sources if s["id"] == ident), None), "install": installed})
        result.append({"id": "xenia", "name": "Xenia / własny adapter", "platform": "xbox360", "install": {"executable": self.preferences()["xenia_path"]} if self.preferences()["xenia_path"] else None,
                       "note": "W tej wersji wskaż lokalny program lub wrapper Xenia. Obsługa i zgodność na Linuxie zależą od wybranego wydania."})
        return result

    def source(self, ident):
        value = self.store.get("sources", ident)
        if not value:
            raise UserError("Nie znaleziono źródła.")
        return value

    def release(self, source, refresh=False):
        cache = source.get("release")
        if not refresh and cache and time.time() - source.get("checked_at", 0) < 900:
            return cache
        try:
            release = latest_release(self.target_source(source))
            self.store.put("sources", source["id"], {**source, "release": release, "checked_at": time.time(), "last_error": None})
            return release
        except Exception as exc:
            self.store.put("sources", source["id"], {**source, "checked_at": time.time(), "last_error": str(exc)})
            raise

    def install(self, source_id, ident=None, review=None, automatic=False, allow_auto=False, *, license_accepted=False, license_hash=None):
        source = self.target_source(self.source(source_id))
        if self.system_key() not in {"linux", "windows", "android"}:
            raise UserError("Obsługiwane systemy: Linux, Windows i Android.")
        if self.system_key() != "android" and host_platform.machine().lower() not in {"x86_64", "amd64"}:
            raise UserError("Te paczki desktop przeznaczone są dla procesorów x86-64.")
        if not source.get("trusted"):
            raise UserError("Źródło nie zostało zatwierdzone do pobierania programów.")
        if source["kind"] == "emulator":
            ident = "engine-" + source_id
            title = source["name"]
        else:
            game = self.require_game(ident)
            if source_id not in game.get("source_ids", []):
                raise UserError("To źródło nie jest przypisane do wybranej gry.")
            title = game["title"]
        with self.process_lock:
            if ident in self.running or any("engine-" + (r.get("engine") or "") == ident for r in self.running.values()):
                raise UserError("Zamknij uruchomioną grę lub emulator przed aktualizacją.")
        old = self.store.get("installs", ident)
        if any(m.get('active') and m.get('game_id')==ident for m in self.store.list('mods')):
            raise UserError('Usuń aktywne mody przed zmianą wersji portu. Zgodność paczek modów jest przypisana do konkretnej wersji.')
        release = self.release(self.source(source_id))
        documents = self.documents.get(source, release)
        if review:
            self.documents.accept(documents, review, auto=allow_auto, license_accepted=license_accepted, license_hash=license_hash)
        if not self.documents.permitted(documents, automatic=automatic):
            return {"review_required":True, "source_id":source_id, "game_id":ident, "documents":documents, "automatic":automatic}
        paths = self.game_location(ident, title, source["platform"] if source["kind"] != "emulator" else "engine", old)
        root = Path(paths["game_root"])

        def work(update, cancelled):
            update(message="Sprawdzanie wydania GitHub", progress=1)
            old_install = self.store.get("installs", ident)
            if old_install and old_install.get("source_id") == source_id and old_install.get("origin_repo") == source["repo"] and old_install.get("version") == release["version"] and Path(old_install.get("runtime_dir", "")).is_dir():
                pending=self.store.get('settings','pending_updates',[])
                self.store.put('settings','pending_updates',[p for p in pending if p.get('target')!=ident])
                return {"message": "Najnowsza wersja jest już zainstalowana.", "install": old_install}
            root.mkdir(parents=True, exist_ok=True)
            Path(paths["user_root"]).mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(root).free < release["asset"]["size"] * 3 + 256 * 1024**2:
                raise UserError("Za mało miejsca na pobranie i rozpakowanie portu.")
            staging = Path(paths["download_root"]) / uuid.uuid4().hex
            staging.mkdir(parents=True)
            try:
                update(message="Sprawdzanie sumy kontrolnej", progress=2)
                checksum = expected_checksum(release)
                asset = release["asset"]
                package = staging / "package.part"
                update(message="Pobieranie " + asset["name"], progress=3)
                sha = download(asset, package,
                    lambda done, total: update(downloaded=done, total=total, progress=3 + round(done / total * 84, 1)), cancelled, checksum)
                if cancelled():
                    raise Cancelled("Anulowano instalację.")
                update(message="Rozpakowywanie portu", progress=90)
                extracted = staging / "runtime"
                extract(package, extracted, asset["name"])
                info_dir = extracted / "Recopile-project-info"
                if info_dir.exists(): raise UserError("Paczka używa zastrzeżonego folderu dokumentacji launchera.")
                info_dir.mkdir()
                for key, filename in [("readme", "README.md"), ("license", "LICENSE")]:
                    if documents[key]["available"]: (info_dir / filename).write_text(documents[key]["text"], encoding="utf-8")
                (info_dir / "project.json").write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
                executable = self._find_executable(source, extracted)
                command = None
                if source.get("adapter") == "flatpak":
                    flatpak = shutil.which("flatpak")
                    packages = list(extracted.rglob("*.flatpak"))
                    if not flatpak or len(packages) != 1:
                        raise UserError("Ten port wymaga polecenia flatpak i jednej paczki .flatpak. Zainstaluj Flatpak i ponów instalację.")
                    update(message="Instalacja Flatpak w profilu użytkownika", progress=94)
                    self._run_task([flatpak, "install", "--user", "--noninteractive", "--assumeyes", "--or-update", str(packages[0])], cancelled, staging / "flatpak.log")
                    command = [flatpak, "run", source["flatpak_id"]]
                suffix = hashlib.sha256((source["repo"] + release["version"] + sha).encode()).hexdigest()[:16]
                target = root / "versions" / (source_id + "-" + suffix)
                target.parent.mkdir(exist_ok=True)
                if target.exists():
                    raise UserError("Ta paczka istnieje już w folderze wersji; poprzednia instalacja pozostaje bez zmian.")
                executable_relative = executable.relative_to(extracted) if executable else None
                extracted.rename(target)
                install = {**{k:v for k,v in paths.items() if k in {"library_root", "game_root", "user_root", "download_root", "manifest"}}, "id": ident, "source_id": source_id, "version": release["version"], "game_root": str(root),
                           "runtime_dir": str(target), "executable": str(target / executable_relative) if executable_relative else "",
                           "command": command, "sha256": sha, "checksum_verified": bool(checksum), "asset": asset["name"],
                           "installed_at": time.time(), "published_at": release.get("published_at"), "ready": source["kind"] == "emulator",
                           "data_path": (old_install or {}).get("data_path", ""), "play_seconds": (old_install or {}).get("play_seconds", 0),
                           "previous_version": old_install, "adapter": source.get("adapter", "native"), "project_documents":documents,"origin_repo":source["repo"]}
                # A manually selected built executable remains usable after updating a
                # project's setup launcher. Never delete/rewrite that executable.
                if (old_install or {}).get("local_executable"):
                    install["local_executable"] = old_install["local_executable"]
                    install["ready"] = True
                if (old_install or {}).get("pinyon_state_root"):
                    install["pinyon_state_root"] = old_install["pinyon_state_root"]
                self.save_install(ident, install)
                pending = self.store.get("settings", "pending_updates", [])
                self.store.put("settings", "pending_updates", [p for p in pending if p.get("target") != ident])
                if not ident.startswith("engine-"):
                    self.add_library(ident)
                update(progress=99, message="Port zainstalowany" if not install["ready"] else "Zainstalowano")
                return {"install": install, "requires_setup": not install["ready"]}
            finally:
                # Only remove our fresh temporary directory, never previous versions,
                # imported images, save data, or a user-selected folder.
                shutil.rmtree(staging, ignore_errors=True)
        return self.jobs.submit("install", title, ident, work)

    @staticmethod
    def _find_executable(source, root):
        adapter = source.get("adapter")
        if adapter == "flatpak":
            return None
        if adapter == "appimage":
            matches = list(root.rglob("*.AppImage"))
        else:
            name = source.get("executable", "")
            if not name:
                matches = list(root.rglob("*.AppImage"))
            elif "/" in name:
                matches = [root / name] if (root / name).is_file() else []
            else:
                matches = [p for p in root.rglob(name) if p.is_file()]
        if len(matches) != 1:
            raise UserError("Nie znaleziono jednoznacznego pliku startowego. Uzupełnij nazwę w źródle lub dodaj własną kompilację.")
        path = matches[0]
        if not path.resolve().is_relative_to(root.resolve()):
            raise UserError("Plik startowy prowadzi poza instalację.")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    @staticmethod
    def _run_task(command, cancelled, log):
        with log.open("w") as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            start = time.monotonic()
            while process.poll() is None:
                if cancelled() or time.monotonic() - start > 1800:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise Cancelled("Przerwano instalację.")
                time.sleep(0.2)
            if process.returncode:
                raise UserError("Instalator zakończył się błędem: " + log.read_text(errors="replace")[-1800:])

    def import_game(self, ident, data):
        game = self.require_game(ident)
        if not data.get("owned"):
            raise UserError("Potwierdź, że wskazujesz swoją kopię gry.")
        path = Path(str(data.get("path", ""))).expanduser().resolve()
        if not path.exists() or not os.access(path, os.R_OK):
            raise UserError("Nie można odczytać wskazanego pliku lub folderu.")
        if game["platform"] == "ps3":
            boot = path / "PS3_GAME/USRDIR/EBOOT.BIN"
            if not boot.is_file():
                boot = path / "USRDIR/EBOOT.BIN"
            if not boot.is_file():
                raise UserError("PS3 wymaga przygotowanego folderu z PS3_GAME/USRDIR/EBOOT.BIN albo USRDIR/EBOOT.BIN. Sam ISO nie jest ścieżką startową RPCS3.")
        elif path.is_file() and path.suffix.lower() not in {".iso", ".bin", ".chd", ".cue", ".xex"}:
            raise UserError("Wskaż obraz ISO/BIN/CHD/CUE, plik XEX lub wypakowany folder gry.")
        elif not path.is_file() and not path.is_dir():
            raise UserError("Niepoprawne źródło danych gry.")
        old = self.store.get("installs", ident) or {"id": ident, **self.game_location(ident, game["title"], game["platform"]), "play_seconds": 0}
        engine = {"ps2": "pcsx2", "ps3": "rpcs3", "xbox360": "xenia"}.get(game["platform"])
        install = {**old, "data_path": str(path), "imported_at": time.time(), "ready": game["kind"] == "emulation", "engine": engine}
        gamefiles = Path(install["game_root"]) / "gamefiles"
        gamefiles.mkdir(parents=True, exist_ok=True)
        link = gamefiles / "input"
        if self.system_key() == "windows":
            (gamefiles / "input.json").write_text(json.dumps({"path":str(path)}), encoding="utf-8")
            self.save_install(ident, install)
            self.add_library(ident)
            return self.store.decorate(self.require_game(ident))
        if link.exists() and not link.is_symlink():
            raise UserError("Plik gamefiles/input nie jest dowiązaniem launchera. Zmień jego nazwę, aby podłączyć kopię gry.")
        temporary = gamefiles / ".input.tmp"
        if temporary.is_symlink():
            temporary.unlink()
        temporary.symlink_to(path, target_is_directory=path.is_dir())
        temporary.replace(link)
        self.save_install(ident, install)
        self.add_library(ident)
        return self.store.decorate(self.require_game(ident))

    def register_executable(self, ident, data):
        game = self.require_game(ident)
        if not data.get("trusted"):
            raise UserError("Potwierdź, że ufasz wskazanemu programowi.")
        path = Path(str(data.get("path", ""))).expanduser().resolve()
        if not path.is_file() or not os.access(path, os.R_OK): raise UserError("Wskaż istniejący, czytelny plik startowy.")
        system=runners.executable_system(path)
        if system=='linux' and not os.access(path,os.X_OK): raise UserError('Program Linux musi mieć prawo wykonywania.')
        mode=data.get('runner','proton' if system=='windows' and self.system_key()=='linux' else 'native')
        if system=='linux' or self.system_key()=='windows': mode='native'
        if mode not in {'proton','wine','native'}: raise UserError('Niepoprawny sposób uruchamiania.')
        install = self.store.get("installs", ident) or {"id": ident, **self.game_location(ident, game["title"], game["platform"]), "play_seconds": 0}
        install = {**install, "local_executable": str(path), "ready": True, "installed_at": time.time(),"local_system":system,"runner":mode,
                   "proton_path":str(data.get('proton_path',''))}
        self.save_install(ident, install)
        self.add_library(ident)
        return self.store.decorate(self.require_game(ident))

    def active_processes(self):
        with self.process_lock:
            return [{"id": ident, "title": info["title"], "started_at": info["started_at"], "pid": info["process"].pid} for ident, info in self.running.items()]

    def launch(self, ident, setup=False, *, benchmark=None):
        game = self.require_game(ident) if not ident.startswith("engine-") else None
        install = self.store.get("installs", ident)
        prefs = self.preferences()
        if not install:
            raise UserError("Najpierw zainstaluj port albo dodaj swoją kopię gry.")
        if game and not setup:
            install = self.game_settings.launch_install(ident, install)
        if game and prefs["only_recompiled"] and game["kind"] != "recompile":
            raise UserError("Aktywny jest tryb tylko rekompilacji. Zmień filtr w ustawieniach, aby użyć innego sposobu uruchamiania.")
        if game and install.get('adapter') == 'steam' and not install.get('local_executable'):
            if setup:
                raise UserError('Ustawienia tej gry zmieniaj w kliencie Steam.')
            return self.steam.launch(ident, install)
        cwd = Path(install.get("runtime_dir") or install.get("game_root") or self.app_root)
        cwd.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
        if game and install.get("local_executable") and not setup:
            command,env = runners.command(install,prefs,env,self.system_key())
            cwd = Path(install["local_executable"]).parent
        elif game and install.get("source_id") == "pinyon" and self.port_setup.supports(self.source("pinyon")):
            if setup: raise UserError("Otwórz panel przygotowania RE:COPILE w szczegółach gry.")
            command, cwd = self.port_setup.launch_command(install)
        elif game and game["kind"] == "emulation":
            data_path = Path(install.get("data_path", ""))
            if not data_path.exists() or not install.get("data_path"):
                raise UserError("Wskaż własne dane gry przed uruchomieniem.")
            engine = next((e for e in self.engines() if e["platform"] == game["platform"]), None)
            if not engine or not engine["install"]:
                raise UserError("Najpierw zainstaluj lub skonfiguruj emulator w zakładce Emulatory.")
            command = [engine["install"]["executable"]]
            if game["platform"] == "ps2":
                engine_data = engine["install"].get("user_root", str(self.store.root / "engine-state/pcsx2"))
                command.extend(["-datapath", engine_data, "-batch", "--", str(data_path)])
            elif game["platform"] == "ps3":
                boot = data_path / "PS3_GAME/USRDIR/EBOOT.BIN"
                if not boot.is_file():
                    boot = data_path / "USRDIR/EBOOT.BIN"
                command.extend(["--no-gui", str(boot)])
            else:
                command.append(str(data_path))
            env = self._engine_env(env, engine["id"])
            cwd = Path(command[0]).parent
        else:
            command = install.get("command") or [install.get("executable", "")]
            if not command[0]:
                raise UserError("Brak pliku startowego. Dodaj lokalną kompilację albo zainstaluj port.")
            if game and not setup and not install.get("ready"):
                raise UserError("Port jest pobrany. Uruchom konfigurację projektu, zbuduj grę i wskaż gotowy plik wykonywalny.")
            if install.get("adapter") == "pinyon-legacy":
                command += ["--state-root", str(Path(install.get("user_root", install["game_root"])) / "preview")]
            elif install.get("adapter") == "pinyon":
                env["PINYON_SHIFT_INSTALL_ROOT"] = str(Path(install["game_root"]) / "content/pinyon")
            elif install.get("adapter") == "native-wizard":
                content = Path(install["game_root"]) / "content"
                content.mkdir(exist_ok=True)
                command += ["--game_data_root=" + str(content)]
            if game and install.get("source_id"):
                user_root = Path(install.get("user_root", install["game_root"]))
                for name, folder in [("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data")]:
                    (user_root / folder).mkdir(parents=True, exist_ok=True)
                    env[name] = str(user_root / folder)
            if ident.startswith("engine-"):
                env = self._engine_env(env, ident.removeprefix("engine-"))
                if ident == "engine-pcsx2":
                    command += ["-datapath", install.get("user_root", str(self.store.root / "engine-state/pcsx2"))]
        if game and not setup:
            command = [*command, *self.game_settings.arguments(ident, install)]
        if not Path(command[0]).is_file() or not os.access(command[0], os.X_OK):
            raise UserError("Program nie istnieje albo nie ma prawa wykonywania.")
        if benchmark:
            command,env = self.performance.wrap(command,env,benchmark)
        with self.process_lock:
            if ident in self.running:
                raise UserError("Ten program jest już uruchomiony.")
            # Engine upgrades are deferred while any game is using that engine.
            active_jobs = self.jobs.list()
            if any(j["status"] in {"running", "queued"} and j["kind"] in {"install", "prepare"} and j["target"] in {ident, "engine-" + (install.get("engine") or "")} for j in active_jobs):
                raise UserError("Poczekaj na zakończenie instalacji.")
            log_dir = self.store.root / "logs"
            log_dir.mkdir(exist_ok=True)
            log = (log_dir / f"launch-{ident}-{int(time.time())}.log").open("w")
            try:
                process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            except Exception:
                log.close()
                raise
            title = game["title"] if game else self.source(ident.removeprefix("engine-"))["name"]
            self.running[ident] = {"process": process, "started_at": time.time(), "started_mono":time.monotonic(), "title": title, "engine": install.get("engine")}
            if game and setup:
                self.save_install(ident, {**install, "setup_started_at": time.time()})
            threading.Thread(target=self._watch, args=(ident, process, log, bool(game) and not setup, self.profiles.active()["id"]), daemon=True).start()
        return {"ok": True, "pid": process.pid}

    def _engine_env(self, env, engine):
        installed = self.store.get("installs", "engine-" + engine, {})
        root = Path(installed.get("user_root", str(self.store.root / "engine-state" / engine)))
        for name, folder in [("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache")]:
            (root / folder).mkdir(parents=True, exist_ok=True)
            env[name] = str(root / folder)
        return env

    def _watch(self, ident, process, log, track, profile_id):
        process.wait()
        log.close()
        self.performance.game_finished(ident)
        with self.process_lock:
            info = self.running.get(ident)
            try:
                if track and info:
                    seconds=max(0,time.monotonic()-info['started_mono'])
                    self.profiles.record(profile_id, self.require_game(ident), seconds, process.returncode)
                    install = self.store.get("installs", ident)
                    if install:
                        self.save_install(ident, {**install, "last_played": info["started_at"], "last_exit_code": process.returncode,
                                                            "play_seconds": install.get("play_seconds", 0) + int(seconds)})
            finally:
                # A finished entry disappears only after its profile is updated.
                self.running.pop(ident,None)

    def check_updates(self, auto=False):
        def work(update, cancelled):
            if self.preferences().get("launcher_repo"):
                update(message="Aktualizowanie katalogu wydawcy", progress=0)
                try: self.sync_catalog()
                except UserError as exc: self.store.put("settings", "catalog_sync", {"time":time.time(), "error":str(exc)})
            sources = self.store.list("sources")
            results = []
            pending = []
            for index, source in enumerate(sources):
                if cancelled():
                    raise Cancelled("Anulowano sprawdzanie aktualizacji.")
                update(message="Sprawdzanie: " + source["name"], progress=round(index / max(len(sources), 1) * 95))
                if source.get("origin") == "development":
                    results.append({"source_id":source["id"],"development":True})
                    continue
                try:
                    release = self.release(source, refresh=True)
                    installed = [i for i in self.store.list("installs") if i.get("source_id") == source["id"]]
                    updates = [i for i in installed if i.get("version") != release["version"] and (not i.get("published_at") or (release.get("published_at") or "") > i["published_at"])]
                    results.append({"source_id": source["id"], "version": release["version"], "updates": [i["id"] for i in updates]})
                    if source.get("channel") != "preview" and source.get("auto_update", True):
                        if updates:
                            documents = self.documents.get(self.target_source(source), release)
                            consent=self.store.get('settings','consent:'+documents['repo'],{})
                            license_doc=documents['license']
                            can_notify=bool(consent.get('auto') and consent.get('license_accepted') is True
                                and license_doc.get('available') and license_doc.get('text','').strip()
                                and license_doc.get('sha256') and consent.get('license_hash')==license_doc['sha256']
                                and documents['readme'].get('available'))
                            pending.extend({"source_id":source["id"], "target":i["id"], "version":release["version"], "name":source["name"],
                                "documents":documents, "notify_only":can_notify, "review_needed":not self.documents.permitted(documents, automatic=True)} for i in updates)
                    if auto and self.preferences()["auto_update"] and source.get("trusted") and source.get("auto_update", True) and source.get("channel") != "preview":
                        for install in updates:
                            with self.process_lock:
                                busy = install["id"] in self.running or any("engine-" + (r.get("engine") or "") == install["id"] for r in self.running.values())
                            if not busy:
                                self.install(source["id"], install["id"], automatic=True)
                except UserError as exc:
                    results.append({"source_id": source["id"], "error": str(exc)})
            self.store.put("settings", "last_update_check", {"time": time.time(), "results": results})
            pending=[p for p in pending if (self.store.get('installs',p['target'],{}).get('version')!=p['version'])]
            self.store.put("settings", "pending_updates", pending)
            if self.preferences().get("launcher_repo"):
                try: self.check_launcher_release()
                except UserError as exc: self.store.put("settings","launcher_update",{"error":str(exc)})
            return results
        return self.jobs.submit("check", "Sprawdzanie aktualizacji", "all-sources", work)

    def apply_pending_updates(self):
        jobs=[]
        if self.preferences()["auto_update"] and not self.documents.app_notice(__version__)["required"]:
            for pending in self.store.get("settings", "pending_updates", []):
                try:
                    result=self.install(pending["source_id"], pending["target"], automatic=True)
                    if not result.get('review_required'): jobs.append(result)
                except UserError: pass
        return jobs

    def _update_loop(self):
        if self.stop.wait(2):
            return
        self.apply_pending_updates()
        if self.preferences()["check_updates"]:
            self.check_updates(auto=False)
        while not self.stop.is_set():
            prefs = self.preferences()
            last = self.store.get("settings", "last_update_check", {}).get("time", 0)
            if prefs["check_updates"] and time.time() - last >= prefs["update_interval_hours"] * 3600:
                self.check_updates(auto=False)
            self.stop.wait(60)

    def rollback(self, ident):
        install = self.store.get("installs", ident)
        previous = (install or {}).get("previous_version")
        with self.process_lock:
            if ident in self.running or any('engine-'+(r.get('engine') or '')==ident for r in self.running.values()):
                raise UserError("Zamknij program przed przywróceniem wersji.")
            if any(j['target']==ident and j['status'] in {'queued','running'} for j in self.jobs.list()):
                raise UserError('Poczekaj na ukończenie instalacji przed przywróceniem wersji.')
            if any(m.get('active') and m.get('game_id')==ident for m in self.store.list('mods')):
                raise UserError('Usuń aktywne mody przed zmianą wersji portu.')
        if not previous:
            raise UserError("Brak poprzedniej wersji.")
        return self.save_install(ident, {**previous, "data_path": install.get("data_path", previous.get("data_path", "")), "play_seconds": install.get("play_seconds", 0)})

    def stage_launcher_update(self):
        repo = self.preferences().get("launcher_repo", "")
        if not repo:
            raise UserError("Najpierw podaj repozytorium wydań tego launchera w ustawieniach.")
        source = {"repo": repo, "asset_pattern": "Recopile-*-linux-x86_64.tar.gz", "scan_releases": True, "allow_prerelease": '-' in __version__}

        def work(update, cancelled):
            release = latest_release(source)
            release_version = release["version"].lstrip("v")
            if version_key(release_version) <= version_key(__version__):
                return {"message": "Launcher jest aktualny."}
            base = self.store.root / "launcher-updates"
            base.mkdir(exist_ok=True)
            stage = base / uuid.uuid4().hex
            stage.mkdir()
            try:
                package = stage / "package.part"
                checksum = expected_checksum(release)
                if not checksum:
                    raise UserError("Aktualizacja launchera wymaga opublikowanej sumy SHA-256.")
                download(release["asset"], package, lambda done, total: update(progress=done / total * 90, downloaded=done, total=total, message="Pobieranie launchera"), cancelled, checksum)
                extract(package, stage / "app", release["asset"]["name"])
                entries = list((stage / "app").rglob("launcher.py"))
                if len(entries) != 1:
                    raise UserError("Paczka aktualizacji nie zawiera jednoznacznego launcher.py.")
                root = entries[0].parent
                if not (root / "recopile/server.py").is_file() or not (root / "frontend/dist/client/index.html").is_file() or not (root / "data/catalog.json.gz").is_file():
                    raise UserError("Paczka aktualizacji launchera jest niekompletna.")
                marker = {"version": release["version"], "root": str(root), "ready": True, "sha256": checksum}
                self.store.put("settings", "launcher_update", marker)
                marker_path = self.store.root / "pending-launcher.json"
                temporary = marker_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(marker))
                temporary.replace(marker_path)
                return {"message": "Nowa wersja zostanie użyta przy następnym starcie.", "version": release["version"]}
            except Exception:
                shutil.rmtree(stage, ignore_errors=True)
                raise
            finally:
                (stage / "package.part").unlink(missing_ok=True)
        return self.jobs.submit("launcher-update", "Aktualizacja launchera", "launcher", work)

    def dump_disc(self, data):
        if self.system_key() != "linux":
            raise UserError("Wbudowany odczyt napędu DVD jest dostępny na Linuxie. Na tym urządzeniu importuj przygotowany obraz według przewodnika.")
        if data.get("platform") != "ps2" or not data.get("owned"):
            raise UserError("Wbudowany odczyt obsługuje czytelne płyty DVD z własnymi grami PS2. Dla Xbox 360 i PS3 użyj przewodników właściwych projektów.")
        device = Path(str(data.get("device", "/dev/sr0"))).resolve()
        if not re.fullmatch(r"/dev/sr[0-9]+", str(device)) or not device.exists() or not stat.S_ISBLK(device.stat().st_mode):
            raise UserError("Wskaż napęd optyczny /dev/sr0, /dev/sr1 itd.")
        if not os.access(device, os.R_OK):
            raise UserError("Brak prawa odczytu napędu. Sprawdź uprawnienia użytkownika do urządzenia.")
        name = str(data.get("filename", "moja-gra.iso")).strip()
        if not re.fullmatch(r"[\w .()\-]{1,180}\.iso", name, re.UNICODE) or name in {".iso", "..iso"}:
            raise UserError("Podaj nazwę pliku ISO bez ścieżki.")
        folder = Path(self.preferences()["games_dir"]) / "recopileapps/discimages"
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / name
        if destination.exists() or destination.with_suffix(".iso.part").exists():
            raise UserError("Plik o tej nazwie już istnieje. Wybierz inną nazwę.")

        def work(update, cancelled):
            import fcntl
            import struct
            partial = destination.with_suffix(".iso.part")
            digest = hashlib.sha256()
            read = 0
            try:
                with device.open("rb", buffering=0) as src, partial.open("xb") as dst:
                    try:
                        total = struct.unpack("Q", fcntl.ioctl(src.fileno(), 0x80081272, bytes(8)))[0]
                    except OSError:
                        total = 0
                    if not total:
                        raise UserError("Napęd nie podał rozmiaru płyty. Włóż czytelną płytę DVD z danymi.")
                    if shutil.disk_usage(folder).free < total + 64 * 1024**2:
                        raise UserError("Za mało miejsca na obraz płyty.")
                    while read < total:
                        if cancelled():
                            raise Cancelled("Anulowano odczyt płyty.")
                        chunk = src.read(min(4 * 1024**2, total - read))
                        if not chunk:
                            raise UserError("Odczyt skończył się przed końcem płyty.")
                        dst.write(chunk)
                        digest.update(chunk)
                        read += len(chunk)
                        update(message="Odczyt płyty DVD", downloaded=read, total=total, progress=round(read / total * 99, 1))
                if destination.exists():
                    raise UserError("Plik docelowy pojawił się w trakcie odczytu; nie został nadpisany.")
                # link() provides a no-overwrite commit even if another process creates
                # the chosen name at the same time.
                os.link(partial, destination)
                partial.unlink()
                digest_path = destination.with_suffix(".iso.sha256")
                digest_path.write_text(digest.hexdigest() + "  " + destination.name + "\n")
                return {"path": str(destination), "sha256": digest.hexdigest(), "bytes": read}
            finally:
                partial.unlink(missing_ok=True)
        return self.jobs.submit("dump", name, str(destination), work)

    def verify_image(self, ident):
        self.require_game(ident)
        install = self.store.get("installs", ident, {})
        path = Path(install.get("data_path", ""))
        if not install.get("data_path") or not path.is_file():
            raise UserError("Najpierw wskaż obraz własnej gry.")
        variants = self.require_game(ident).get("variants", [])
        def work(update, cancelled):
            digest = hashlib.sha1()
            sha256 = hashlib.sha256()
            total = path.stat().st_size
            read = 0
            with path.open("rb") as src:
                while chunk := src.read(4 * 1024**2):
                    if cancelled():
                        raise Cancelled("Anulowano sprawdzanie obrazu.")
                    digest.update(chunk)
                    sha256.update(chunk)
                    read += len(chunk)
                    update(message="Sprawdzanie obrazu", downloaded=read, total=total, progress=read / max(total, 1) * 99)
            matches = [v for v in variants if v.get("sha1") == digest.hexdigest()]
            result = {"sha1": digest.hexdigest(), "sha256": sha256.hexdigest(), "catalog_match": bool(matches), "variants": matches,
                      "message": "Obraz pasuje do wariantu w katalogu." if matches else "Brak dopasowania sumy w katalogu. To nie rozstrzyga zgodności obrazu z portem; zweryfikuje go instalator projektu."}
            current = self.store.get("installs", ident)
            self.save_install(ident, {**current, "image_verification": result})
            return result
        return self.jobs.submit("verify", "Weryfikacja obrazu", ident, work)

    def shutdown(self):
        self.stop.set()
        self.performance.shutdown()
        self.media.shutdown()
        self.jobs.shutdown()
