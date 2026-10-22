from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from .technologies import declared, TECHNOLOGIES, TAGS


def search_key(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text).casefold() if c.isalnum())


def game_id(platform: str, title: str) -> str:
    return platform + "-" + hashlib.sha256(search_key(title).encode()).hexdigest()[:16]


class Store:
    def __init__(self, app_root: Path, state_root: Path):
        self.app_root = app_root
        self.root = state_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "library.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, platform TEXT NOT NULL,
                    search TEXT NOT NULL, payload TEXT NOT NULL, rank INTEGER NOT NULL DEFAULT 99999,
                    kind TEXT NOT NULL DEFAULT 'emulation', added INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS games_platform ON games(platform,kind);
                CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS installs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profile_stats (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS achievements (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS compatibility_reports (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS mods (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS game_media (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS benchmarks (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)
        self._seed()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _seed(self):
        registry = json.loads((self.app_root / "data/registry.json").read_text())
        fingerprint = hashlib.sha256((self.app_root / "data/catalog.json.gz").read_bytes()).hexdigest()
        if self.get("settings", "catalog_hash") != fingerprint:
            with gzip.open(self.app_root / "data/catalog.json.gz", "rt", encoding="utf-8") as stream:
                catalog = json.load(stream)
            with self.connect() as db:
                for game in catalog["games"]:
                    lookup = search_key(game["title"] + " " + " ".join(v["name"] + " " + v["serial"] for v in game["variants"]))
                    db.execute("INSERT INTO games(id,title,platform,search,payload,kind) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET search=excluded.search",
                               (game["id"], game["title"], game["platform"], lookup, json.dumps(game, ensure_ascii=False), game.get("kind", "emulation")))
            self.put("settings", "catalog", {"imported_at": catalog["imported_at"], "sources": catalog["sources"], "snapshot_titles": len(catalog["games"]), "hash": fingerprint})
            self.put("settings", "catalog_hash", fingerprint)
        # Only seed shipped sources once. User edits survive new launcher versions.
        for source in registry["sources"]:
            current = self.get("sources", source["id"])
            # An earlier preview incorrectly branded the independent Pinyon
            # project. Remove only that generated label; retain custom URLs.
            if current and source['id']=='pinyon' and current.get('edition')=='recopile':
                current.pop('edition',None)
                if current.get('name')=='Pinyon Shift · RE:COPILE Edition': current['name']='Pinyon Shift'
                self.put('sources',source['id'],current)
            if not current:
                self.put("sources", source["id"], {**source, "trusted": bool(source.get("verified")), "verified_at": registry["verified_at"]})
            elif not current.get("user_override") and not current.get('catalog_repo'):
                # Shipped channel labels follow the maintained registry; release
                # cache and a user's asset/executable configuration remain intact.
                labels = {k: v for k, v in source.items() if k in {"name", "repo", "guide", "note", "channel", "supported", "auto_update", "archived", "assets_by_system", "executables_by_system", "repos_by_system", "release_tags_by_system", "documentation_repo", "documentation_ref", "development_status", "experimental_systems", "edition", "technologies", "origin", "download_page", "author", "manual_systems"}}
                self.put("sources", source["id"], {**current, **labels})
        for featured in registry["featured"]:
            ident = game_id(featured["platform"], featured["match"])
            existing = self.game(ident)
            if existing and existing.get('catalog_repo'):
                continue  # A downloaded catalog survives an offline restart.
            if not existing:
                existing = {"id": ident, "title": featured["title"], "platform": featured["platform"], "variants": []}
            game = {**existing, **{k: v for k, v in featured.items() if k not in {"match", "source_ids"}}}
            game["source_ids"] = list(dict.fromkeys([*featured.get("source_ids", []), *existing.get("source_ids", [])]))
            source_ids = game.get("source_ids", [])
            kinds = [self.get("sources", s, {}).get("kind") for s in source_ids]
            kind = "recompile" if "recompile" in kinds else "native" if "native" in kinds else "emulation"
            self.save_game({**game, "kind": kind, "rank": featured["rank"]})
        distribution_path = self.app_root / "data/distribution.json"
        distribution = json.loads(distribution_path.read_text()) if distribution_path.is_file() else {}
        default_library = os.environ.get("RECOPILE_LIBRARY_ROOT", str(self.app_root / "RecopileLibrary"))
        defaults = {"games_dir": default_library, "libraries": [default_library], "only_recompiled": False,
                "check_updates": True, "auto_update": True, "update_interval_hours": 6,
                "bios_path": "", "xenia_path": "", "launcher_repo": distribution.get("repo", ""), "profile_name": "Gracz",
                "active_profile": "local", "discord_url": distribution.get("discord_url", ""),
                "onboarding_complete": False, "last_notice_version": "", "accepted_app_license":"", "android_ads": False, "proton_path":"", "umu_path":"", "language":"en", "steam_libraries":[], "steam_enabled":False}
        preferences={**defaults, **self.get("settings", "preferences", {})}
        preferences.pop("publisher_mode",None)
        self.put("settings", "preferences", preferences)
        if not self.get("profiles", "local"):
            self.put("profiles", "local", {"id": "local", "name": self.get("settings", "preferences")["profile_name"], "created_at": time.time()})
        for job in self.list("jobs"):
            if job["status"] in ("queued", "running"):
                self.put("jobs", job["id"], {**job, "status": "interrupted", "message": "Przerwano przy zamknięciu launchera. Uruchom zadanie ponownie.", "finished_at": time.time()})

    def get(self, table: str, ident: str, default=None):
        self._table(table)
        with self.connect() as db:
            row = db.execute(f"SELECT payload FROM {table} WHERE id=?", (ident,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, table: str, ident: str, value):
        self._table(table)
        with self.connect() as db:
            db.execute(f"INSERT INTO {table}(id,payload) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (ident, json.dumps(value, ensure_ascii=False)))
        return value

    def delete(self, table: str, ident: str):
        self._table(table)
        with self.connect() as db:
            db.execute(f"DELETE FROM {table} WHERE id=?", (ident,))

    def list(self, table: str):
        self._table(table)
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute(f"SELECT payload FROM {table}")]

    @staticmethod
    def _table(table):
        if table not in {"sources", "installs", "jobs", "settings", "profiles", "profile_stats", "achievements", "compatibility_reports", "mods", "game_media", "benchmarks"}:
            raise ValueError("Niepoprawna tabela")

    def game(self, ident: str):
        with self.connect() as db:
            row = db.execute("SELECT payload,kind,added FROM games WHERE id=?", (ident,)).fetchone()
        return {**json.loads(row[0]), "kind": row[1], "added": bool(row[2])} if row else None

    def save_game(self, game):
        lookup = search_key(game["title"] + " " + " ".join(v.get("name", "") + " " + v.get("serial", "") for v in game.get("variants", [])))
        capabilities = declared(game,[self.get('sources',s,{}) for s in game.get('source_ids',[])])
        lookup += search_key(' '.join(t['label'] for t in capabilities)+' '+' '.join(TAGS.get(t,t) for t in game.get('tags',[])))
        with self.connect() as db:
            db.execute("""INSERT INTO games(id,title,platform,search,payload,rank,kind,added) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title,platform=excluded.platform,search=excluded.search,
                payload=excluded.payload,rank=excluded.rank,kind=excluded.kind,added=excluded.added""",
                (game["id"], game["title"], game["platform"], lookup, json.dumps(game, ensure_ascii=False), game.get("rank", 99999), game.get("kind", "emulation"), int(game.get("added", False))))
        return game

    def steam_games(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload,kind,added FROM games WHERE platform='other'").fetchall()
        games = [{**json.loads(row[0]), 'kind':row[1], 'added':bool(row[2])} for row in rows]
        return [game for game in games if game.get('steam_app_id') or game['id'].startswith('steam-')]

    def delete_game(self, ident):
        with self.connect() as db:
            db.execute('DELETE FROM games WHERE id=?', (ident,))

    def device_candidates(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload,kind,added FROM games WHERE kind IN ('native','recompile') OR id IN (SELECT id FROM installs)").fetchall()
        return [self.decorate({**json.loads(r[0]), "kind": r[1], "added": bool(r[2])}) for r in rows]

    def query(self, q="", platform="all", mode="all", view="catalog", sort="featured", limit=24, offset=0, eligible_ids=None):
        clauses, params = [], []
        if eligible_ids is not None:
            clauses.append("id IN (" + ",".join("?" for _ in eligible_ids) + ")" if eligible_ids else "0")
            params.extend(eligible_ids)
        if q:
            clauses.append("search LIKE ?")
            params.append("%" + search_key(q) + "%")
        if platform != "all":
            clauses.append("platform=?")
            params.append(platform)
        if mode == "recompile":
            clauses.append("kind='recompile'")
        elif mode == "emulation":
            clauses.append("kind='emulation'")
        if view == "library":
            clauses.append("(added=1 OR id IN (SELECT id FROM installs))")
        elif view == "installed":
            clauses.append("id IN (SELECT id FROM installs)")
        elif view == "other":
            clauses.append("platform='other'")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        order = {"title": "title COLLATE NOCASE", "platform": "platform,rank,title COLLATE NOCASE"}.get(sort, "rank,title COLLATE NOCASE")
        with self.connect() as db:
            total = db.execute("SELECT COUNT(*) FROM games" + where, params).fetchone()[0]
            rows = db.execute("SELECT payload,kind,added FROM games" + where + " ORDER BY " + order + " LIMIT ? OFFSET ?", (*params, min(max(int(limit), 1), 100), max(int(offset), 0))).fetchall()
        games = [{**json.loads(r[0]), "kind": r[1], "added": bool(r[2])} for r in rows]
        return {"games": [self.decorate(g) for g in games], "total": total, "offset": int(offset)}

    def decorate(self, game):
        install = self.get("installs", game["id"])
        if install and game.get("kind") == "emulation" and not install.get("local_executable"):
            engine = install.get("engine", "")
            available = bool(self.get("installs", "engine-" + engine)) if engine != "xenia" else bool(self.get("settings", "preferences", {}).get("xenia_path"))
            install = {**install, "ready": bool(install.get("data_path")) and available}
        source_ids = game.get("source_ids", [])
        sources = [self.get("sources", ident) for ident in source_ids]
        sources = [s for s in sources if s]
        result = {**game, "sources": sources, "install": install, "variant_count": len(game.get("variants", []))}
        result['declared_technologies'] = declared(game,sources)
        if game.get("cover") and any((self.app_root / folder / game["cover"]).is_file() for folder in ("frontend/public/assets/covers", "frontend/dist/client/assets/covers")):
            result["cover_url"] = "/assets/covers/" + game["cover"]
        media = self.get("game_media", game["id"], {})
        for key in ("description", "description_url", "description_license"):
            if media.get(key) and not result.get(key): result[key] = media[key]
        if media.get("cover_file") and (self.root / "covers" / media["cover_file"]).is_file():
            result["cover_url"] = "/api/covers/" + media["cover_file"]
            result["cover_source_url"] = media.get("description_url")
        result["media_status"] = {"description": media.get("description_status", "idle"), "cover": media.get("cover_status", "idle")}
        # Lists stay small; all variants are provided only by the detail endpoint.
        result.pop("variants", None)
        return result

    def stats(self):
        with self.connect() as db:
            platforms = dict(db.execute("SELECT platform,COUNT(*) FROM games GROUP BY platform"))
            recomp = db.execute("SELECT COUNT(*) FROM games WHERE kind='recompile'").fetchone()[0]
            library = db.execute("SELECT COUNT(*) FROM games WHERE added=1 OR id IN (SELECT id FROM installs)").fetchone()[0]
        installs = self.list("installs")
        return {"total": sum(platforms.values()), "platforms": platforms, "recompiled": recomp, "library": library,
                "installed": sum(not i["id"].startswith("engine-") for i in installs),
                "ready": sum(i.get("ready", False) and not i["id"].startswith("engine-") for i in installs), "sources": len(self.list("sources"))}
