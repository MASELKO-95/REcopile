"""Read public project lists as metadata, never as installation instructions.

Copyright (C) 2026 MASELKO-95. GPL-3.0-only. Added 2026-10-30.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .network import Cancelled, UserError, validate_repo
from .storage import game_id, search_key

LISTS = (
    {"id": "awesome-x360", "name": "Awesome Xbox 360 Recomps",
     "url": "https://github.com/abduznik/awesome-x360-recomps",
     "feed": "https://raw.githubusercontent.com/abduznik/awesome-x360-recomps/HEAD/README.md"},
    {"id": "portedgames-x360", "name": "PortedGames · Xbox 360",
     "url": "https://portedgames.com/recompiled-games/xbox-360/",
     "feed": "https://portedgames.com/recompiled-games/xbox-360/"},
)
LISTED_NOTE = "Projekt znaleziony na śledzonej liście. Instrukcja instalacji i aktualne wydania są u autora. Paczka dla RE:COPILE i działanie gry nie zostały zweryfikowane."


def repo_link(url):
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or parsed.query or parsed.fragment:
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2:
        return None
    try:
        return validate_repo("/".join(parts))
    except UserError:
        return None


def clean_title(title):
    title = re.sub(r"\s*\((?:XBLA|Android|iOS|Xbox 360 version|2005, Xbox 360)\)\s*$", "", title, flags=re.I)
    return " ".join(title.split()).strip()


def checked_entries(entries):
    result = {}
    for entry in entries:
        title, repo = clean_title(entry["title"]), entry["repo"]
        if not 1 <= len(title) <= 200 or any(ord(c) < 32 for c in title):
            continue
        repo = validate_repo(repo)
        result.setdefault(repo.casefold(), {"title": title, "repo": repo})
    if not result or len(result) > 1000:
        raise UserError("Nie udało się odczytać listy projektów. Zachowano poprzednią listę.")
    return list(result.values())


def parse_markdown(text):
    entries = []
    for line in text.splitlines():
        # Only the first cell of a project table, never credits or SDK links.
        match = re.match(r"^\s*\|\s*\[([^\]]+)\]\((https://github\.com/[^\s)]+)\)\s*\|", line)
        if match and (repo := repo_link(match[2])):
            entries.append({"title": match[1], "repo": repo})
    return checked_entries(entries)


class ProjectTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.entries, self.guides, self.cells, self.cell, self.links = [], [], [], None, []
        self.guide = None
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.cells, self.links = [], []
            self.guide = None
        elif tag == "td":
            self.cell = []
        elif tag == "div" and self.cell is not None:
            self.ignored_depth += 1
        elif tag == "a" and self.cell is not None:
            repo = repo_link(attrs.get("href", ""))
            if repo:
                self.links.append(repo)
            elif re.fullmatch(r'/[a-z0-9-]+/', attrs.get('href', '')):
                self.guide = 'https://portedgames.com' + attrs['href']

    def handle_data(self, data):
        if self.cell is not None and not self.ignored_depth:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "div" and self.ignored_depth:
            self.ignored_depth -= 1
        elif tag == "td" and self.cell is not None:
            self.cells.append(" ".join(self.cell).strip())
            self.cell, self.ignored_depth = None, 0
        elif tag == "tr" and len(self.cells) >= 2 and self.cells[1] == "Xbox 360":
            for repo in self.links:
                self.entries.append({"title": self.cells[0], "repo": repo})
            if not self.links and self.guide and len(self.cells) > 2:
                self.guides.append({'title': self.cells[0], 'project': self.cells[2], 'url': self.guide})


def parse_html(text, guides=None):
    parser = ProjectTable()
    parser.feed(text)
    for guide in parser.guides:
        repos = (guides or {}).get(guide['url'], [])
        exact = [repo for repo in repos if search_key(repo.split('/')[1]) == search_key(guide['project'])]
        for repo in (exact or repos[:1]):
            parser.entries.append({'title': guide['title'], 'repo': repo})
    return checked_entries(parser.entries)


class GuideLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.repos = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a' and (repo := repo_link(dict(attrs).get('href', ''))):
            if repo not in self.repos:
                self.repos.append(repo)


def guide_url(url):
    return bool(re.fullmatch(r'https://portedgames\.com/[a-z0-9-]+/', url))


class ListRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if newurl not in {item["feed"] for item in LISTS} and not guide_url(newurl):
            raise UserError("Lista projektów przekierowała na nieobsługiwany adres.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_list(spec):
    if spec["feed"] not in {item["feed"] for item in LISTS} and not guide_url(spec['feed']):
        raise UserError("Nieobsługiwana lista projektów.")
    try:
        request = Request(spec["feed"], headers={"User-Agent": "RE-COPILE-Catalog/1.0"})
        with build_opener(ListRedirect()).open(request, timeout=20) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise UserError("Lista projektów jest zbyt duża.")
        return raw.decode("utf-8")
    except (URLError, TimeoutError, OSError, UnicodeError) as exc:
        raise UserError("Nie udało się sprawdzić listy projektów. Zachowano jej lokalną kopię.") from exc


def source_id(repo):
    return "list-" + hashlib.sha256(repo.casefold().encode()).hexdigest()[:20]


def reference_source(entry):
    return {"id": source_id(entry["repo"]), "name": entry["title"], "repo": entry["repo"],
            "platform": "xbox360", "kind": "recompile", "origin": "development",
            "development_status": "listed", "asset_pattern": "", "assets_by_system": {},
            "executables_by_system": {}, "adapter": "native", "verified": False,
            "auto_update": False, "guide": "https://github.com/" + entry["repo"],
            "discover_packages": True,
            "note": LISTED_NOTE, "technologies": ["static-recompilation"]}


class CatalogLists:
    def __init__(self, launcher):
        self.app, self.store = launcher, launcher.store
        self.lock = threading.RLock()
        registry = json.loads((launcher.app_root / "data/registry.json").read_text())
        for snapshot in registry.get("tracked_lists", []):
            if snapshot.get("id") in {s["id"] for s in LISTS} and not self.store.get("settings", "list:" + snapshot["id"]):
                self.store.put("settings", "list:" + snapshot["id"], snapshot)

    def _sources_and_games(self):
        sources = {s.get("repo", "").casefold(): s for s in reversed(self.store.list("sources")) if s.get("repo")}
        with self.store.connect() as db:
            games = [json.loads(row[0]) for row in db.execute("SELECT payload FROM games WHERE platform='xbox360'")]
        by_title = {search_key(clean_title(g["title"])): g for g in games}
        attached = {s: g["id"] for g in games for s in g.get("source_ids", [])}
        return sources, by_title, attached

    def state(self, details=False):
        sources, games, attached = self._sources_and_games()
        lists = []
        for spec in LISTS:
            saved = self.store.get("settings", "list:" + spec["id"], {})
            entries = [{**e, "source_id": sources.get(e["repo"].casefold(), {}).get("id"),
                        "game_id": attached.get(sources.get(e["repo"].casefold(), {}).get("id"))}
                       for e in saved.get("entries", [])]
            missing = sum(not e["game_id"] for e in entries)
            lists.append({"id": spec["id"], "name": spec["name"], "url": spec["url"],
                          "checked_at": saved.get("checked_at"), "error": saved.get("error"),
                          "total": len(entries), "missing": missing,
                          **({"entries": entries} if details else {})})
        return {"lists": lists, "enabled": self.app.preferences().get("track_catalog_lists", True)}

    def include(self, entries, list_id):
        from .registry import FIELDS, validate_registry
        sources, games, attached = self._sources_and_games()
        added = 0
        for entry in checked_entries(entries):
            source = sources.get(entry["repo"].casefold())
            if source and source["id"] in attached:
                continue
            source = source or reference_source(entry)
            title_key = search_key(clean_title(entry["title"]))
            game = games.get(title_key) or {"id": game_id("xbox360", entry["title"]),
                    "title": entry["title"], "platform": "xbox360", "variants": [], "rank": 300}
            validate_registry({"schema_version": 1, "sources": [{k: v for k, v in source.items()
                if k in FIELDS}],
                "featured": [{"title": game["title"], "platform": "xbox360", "source_ids": [source["id"]]}]})
            if entry["repo"].casefold() not in sources:
                self.store.put("sources", source["id"], {**source, "tracked_list": list_id})
                sources[entry["repo"].casefold()] = source
            self.store.save_game({**game, "kind": "recompile", "source_ids": list(dict.fromkeys([
                *game.get("source_ids", []), source["id"]]))})
            games[title_key], attached[source["id"]] = self.store.game(game["id"]), game["id"]
            added += 1
        return added

    def sync(self, update=None, cancelled=lambda: False):
        with self.lock:
            added = 0
            for spec in LISTS:
                if cancelled():
                    raise Cancelled("Anulowano sprawdzanie list projektów.")
                if update:
                    update(message="Sprawdzanie listy: " + spec["name"])
                previous = self.store.get("settings", "list:" + spec["id"], {})
                try:
                    text = fetch_list(spec)
                    guides = dict(previous.get('guides', {}))
                    if spec['id'] == 'portedgames-x360':
                        parser = ProjectTable()
                        parser.feed(text)
                        for url in dict.fromkeys(g['url'] for g in parser.guides):
                            if cancelled():
                                raise Cancelled('Anulowano sprawdzanie list projektów.')
                            try:
                                links = GuideLinks()
                                links.feed(fetch_list({'feed': url}))
                                if links.repos: guides[url] = links.repos
                            except Cancelled:
                                raise
                            except UserError:
                                if url not in guides: raise
                    entries = parse_markdown(text) if spec["id"] == "awesome-x360" else parse_html(text, guides)
                    added += self.include(entries, spec["id"])
                    self.store.put("settings", "list:" + spec["id"], {"id": spec["id"],
                        "entries": entries, "guides": guides, "checked_at": time.time(), "error": None})
                except Cancelled:
                    raise
                except UserError as exc:
                    self.store.put("settings", "list:" + spec["id"], {**previous, "error": str(exc)})
            return {**self.state(), "added": added}

    def check(self):
        return self.app.jobs.submit("catalog-lists", "Sprawdzanie list projektów", "catalog-lists",
                                    lambda update, cancelled: self.sync(update, cancelled))

    def add_cached(self, data):
        with self.lock:
            if data.get('list_id') not in {s['id'] for s in LISTS}:
                raise UserError('Nieobsługiwana lista projektów.')
            saved = self.store.get('settings', 'list:' + data['list_id'], {})
            entry = next((e for e in saved.get('entries', []) if e['repo'] == data.get('repo')), None)
            if not entry:
                raise UserError('Nie znaleziono projektu na zapisanej liście.')
            self.include([entry], data['list_id'])
            sources, _, attached = self._sources_and_games()
            return {'game_id': attached.get(sources[entry['repo'].casefold()]['id'])}
