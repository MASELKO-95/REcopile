"""Small, on-demand Wikipedia text and artwork cache. No catalog-wide crawl."""
from __future__ import annotations

import hashlib
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image

from .network import UserError
from .storage import search_key

USER_AGENT = "Recopile-Games-Hub/0.1 (https://github.com/MASELKO-95/recopile)"


def validate_media_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"en.wikipedia.org", "upload.wikimedia.org"} or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise UserError("Niedozwolony adres metadanych lub okładki.")


class MediaRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_media_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_media(url, maximum):
    validate_media_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with build_opener(MediaRedirect()).open(request, timeout=12) as response:
        raw = response.read(maximum + 1)
    if len(raw) > maximum: raise UserError("Odpowiedź z metadanymi lub okładką jest zbyt duża.")
    return raw


def wikipedia_metadata(game):
    title = unquote(game.get("wiki_title") or game["title"]).replace("_", " ")
    candidates = list(dict.fromkeys([title + " (video game)", title]))
    params = {"action": "query", "format": "json", "formatversion": 2, "redirects": 1,
        "titles": "|".join(candidates), "prop": "extracts|pageimages|pageprops", "exintro": 1,
        "explaintext": 1, "exlimit": "max", "exchars": 1200, "piprop": "thumbnail", "pithumbsize": 480, "pilicense": "any"}
    data = json.loads(read_media("https://en.wikipedia.org/w/api.php?" + urlencode(params), 2_000_000))
    if data.get("error"): raise UserError("Nie udało się pobrać opisu z Wikipedii.")
    pages = data.get("query", {}).get("pages", [])
    redirects = {item["to"] for item in data.get("query", {}).get("redirects", [])}
    expected = {search_key(t) for t in candidates} | {search_key(t) for t in redirects}
    for page in sorted(pages, key=lambda p: "(video game)" not in p.get("title", "")):
        props = page.get("pageprops", {})
        text = page.get("extract", "").strip()
        if "missing" in page or "disambiguation" in props or not text or search_key(page["title"]) not in expected:
            continue
        # Avoid attaching a film, novel, or a whole franchise to a single game.
        if "game" not in (props.get("wikibase-shortdesc", "") + " " + text[:350]).casefold(): continue
        return {"description": text, "description_url": "https://en.wikipedia.org/wiki/" + quote(page["title"].replace(" ", "_"), safe=""),
            "description_license": "CC BY-SA 4.0 · Wikipedia contributors", "thumbnail": page.get("thumbnail", {}).get("source")}
    return {}


class GameMedia:
    def __init__(self, store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="recopile-media")
        self.lock = threading.RLock()
        self.pending = {}
        self.revision = 0
        self.closed = False

    def shipped_cover(self, game):
        return bool(game.get("cover") and (self.store.app_root / "frontend/public/assets/covers" / game["cover"]).is_file()) or bool(game.get("cover") and (self.store.app_root / "frontend/dist/client/assets/covers" / game["cover"]).is_file())

    def cached_cover(self, cache):
        return bool(cache.get("cover_file") and (self.store.root / "covers" / cache["cover_file"]).is_file())

    @staticmethod
    def due(cache, field):
        status = cache.get(field + "_status")
        if status == "ready": return False
        delay = 600 if status == "error" else 7 * 86400
        return not cache.get(field + "_checked") or time.time() - cache[field + "_checked"] >= delay

    def request(self, games, covers=False):
        queued = 0
        with self.lock:
            if self.closed: return {"queued": 0}
            for game in games:
                ident = game["id"]
                cache = self.store.get("game_media", ident, {})
                need_cover = covers and not self.shipped_cover(game) and not self.cached_cover(cache) and (cache.get("cover_status") == "ready" or self.due(cache, "cover"))
                if not self.due(cache, "description") and not need_cover: continue
                if ident in self.pending:
                    self.pending[ident] = self.pending[ident] or covers
                    continue
                self.pending[ident] = covers
                self.pool.submit(self._work, game)
                queued += 1
        return {"queued": queued}

    def _save(self, ident, cache):
        self.store.put("game_media", ident, cache)
        with self.lock: self.revision += 1

    def _work(self, game):
        ident = game["id"]
        finished = False
        try:
            while True:
                with self.lock:
                    if self.closed: return
                    covers = self.pending[ident]
                cache = self.store.get("game_media", ident, {})
                if self.due(cache, "description"):
                    try:
                        metadata = wikipedia_metadata(game)
                        cache.update(metadata)
                        cache.update(description_status="ready" if metadata else "missing", description_checked=time.time())
                    except (OSError, ValueError, UserError):
                        cache.update(description_status="error", description_checked=time.time())
                    self._save(ident, cache)
                if covers and not self.shipped_cover(game) and not self.cached_cover(cache) and (cache.get("cover_status") == "ready" or self.due(cache, "cover")):
                    try:
                        if cache.get("description_status") == "error": raise UserError("Opis chwilowo niedostępny.")
                        if cache.get("thumbnail"):
                            self._download_cover(ident, cache)
                            cache["cover_status"] = "ready"
                        else:
                            cache["cover_status"] = "missing"
                    except (OSError, ValueError, UserError, Image.DecompressionBombError):
                        cache["cover_status"] = "error"
                    cache["cover_checked"] = time.time()
                    self._save(ident, cache)
                with self.lock:
                    if self.pending[ident] == covers:
                        self.pending.pop(ident)
                        finished = True
                        return
        finally:
            if not finished:
                with self.lock: self.pending.pop(ident, None)

    def _download_cover(self, ident, cache):
        url = cache["thumbnail"]
        if urlparse(url).hostname != "upload.wikimedia.org": raise UserError("Niedozwolone źródło okładki.")
        raw = read_media(url, 5_000_000)
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 12_000_000 or image.format not in {"PNG", "JPEG", "WEBP"}:
                raise UserError("Nieobsługiwany format okładki.")
            suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image.format]
            image.verify()
        filename = hashlib.sha256(ident.encode() + raw).hexdigest() + suffix
        folder = self.store.root / "covers"
        folder.mkdir(exist_ok=True)
        temporary = folder / (filename + ".part")
        temporary.write_bytes(raw)
        temporary.replace(folder / filename)
        cache["cover_file"] = filename

    def shutdown(self):
        with self.lock: self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
