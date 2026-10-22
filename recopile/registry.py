"""Validate publisher metadata. A catalog never contains executable commands."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from .network import UserError, validate_repo
from .platforms import PLATFORMS
from .technologies import validate_labels

FIELDS = {"id", "name", "repo", "platform", "kind", "asset_pattern", "assets_by_system", "exclude_pattern", "executable", "executables_by_system", "repos_by_system", "documentation_repo", "documentation_ref", "adapter", "flatpak_id", "verified", "archived", "channel", "supported", "auto_update", "guide", "note", "mod_root", "origin", "development_status", "experimental_systems", "edition", "public_listing"}
FIELDS.add('technologies')
FIELDS.add('release_tags_by_system')
FIELDS.update({'download_page', 'author', 'manual_systems'})

def validate_registry(value):
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise UserError("Nieobsługiwana wersja katalogu.")
    sources, games = value.get("sources"), value.get("featured")
    if not isinstance(value.get('catalog_version',''),str) or len(value.get('catalog_version',''))>80 or not isinstance(value.get('catalog_notes',''),str) or len(value.get('catalog_notes',''))>16000:
        raise UserError('Niepoprawna wersja lub opis aktualizacji katalogu.')
    if not isinstance(sources, list) or not isinstance(games, list) or max(len(sources), len(games)) > 2000:
        raise UserError("Niepoprawny katalog.")
    seen = set()
    for source in sources:
        if not isinstance(source,dict): raise UserError('Niepoprawne źródło katalogu.')
        validate_labels(source,'technologies')
        ident = source.get("id", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", ident) or ident in seen:
            raise UserError("Niepoprawny lub powtórzony identyfikator źródła.")
        seen.add(ident)
        development = source.get("origin") == "development"
        external = source.get("origin") == "external"
        if external:
            page = source.get('download_page', '')
            if not isinstance(page, str) or len(page) > 1000 or any(c.isspace() for c in page):
                raise UserError('Niepoprawna strona pobierania autora.')
            try:
                url = urlsplit(page)
                valid = (url.scheme == 'https' and url.hostname and '.' in url.hostname
                         and not url.username and not url.password and not url.query
                         and url.port in (None, 443))
            except ValueError:
                valid = False
            if not valid:
                raise UserError('Podaj stałą stronę pobierania HTTPS bez tokenów ani danych logowania.')
            author = source.get('author', '')
            if not isinstance(author, str) or not 1 <= len(author) <= 120 or any(ord(c) < 32 or c in '|[]' for c in author):
                raise UserError('Podaj autora zewnętrznego projektu.')
            if source.get('auto_update', True) or source.get('asset_pattern') or source.get('assets_by_system') or source.get('repos_by_system') or source.get('release_tags_by_system'):
                raise UserError('Zewnętrzne pobieranie jest ręczne i nie używa paczek GitHub.')
        systems = source.get('manual_systems', [])
        if not isinstance(systems, list) or any(not isinstance(s, str) or s not in {'linux', 'windows', 'android'} for s in systems) or (systems and not external) or (external and not systems):
            raise UserError('Niepoprawna lista systemów ręcznego pobierania.')
        if source.get("edition") not in (None, "recopile"):
            raise UserError("Niepoprawne oznaczenie edycji.")
        systems = source.get("experimental_systems", [])
        if not isinstance(systems, list) or any(not isinstance(s, str) or s not in {"linux", "windows", "android"} for s in systems):
            raise UserError("Niepoprawna lista systemów eksperymentalnego projektu.")
        if source.get("repo") or not (development or external): validate_repo(source.get("repo", ""))
        for mapping in ["assets_by_system", "executables_by_system", "repos_by_system", "release_tags_by_system"]:
            if not isinstance(source.get(mapping, {}), dict) or any(k not in {"linux", "windows", "android"} for k in source.get(mapping, {})):
                raise UserError("Niepoprawna mapa obsługiwanych systemów.")
        for repo in [*source.get("repos_by_system", {}).values(), *([source["documentation_repo"]] if source.get("documentation_repo") else [])]: validate_repo(repo)
        if any(not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", tag)
               for tag in source.get("release_tags_by_system", {}).values()):
            raise UserError("Niepoprawny tag wydania portu.")
        mod_root = source.get("mod_root", "")
        if mod_root and (not isinstance(mod_root,str) or Path(mod_root).is_absolute() or ".." in Path(mod_root).parts or "\\" in mod_root or ":" in mod_root or Path(mod_root).parts[0] not in {"mods","content"}):
            raise UserError("Folder modów musi leżeć wewnątrz mods/ lub content/ gry.")
        if source.get("platform") not in PLATFORMS or source.get("kind") not in {"native", "recompile", "emulator"}:
            raise UserError("Niepoprawna platforma lub rodzaj portu.")
        patterns = [source.get("asset_pattern", ""), *source.get("assets_by_system", {}).values()]
        if any(not isinstance(p, str) or (not p and not (development or external)) or len(p) > 200 or "/" in p or "\\" in p for p in patterns):
            raise UserError("Niepoprawny wzorzec paczki wydania.")
        executables = [source.get("executable", ""), *source.get("executables_by_system", {}).values()]
        if any(not isinstance(p, str) or Path(p).is_absolute() or ".." in Path(p).parts or "\\" in p or ':' in p for p in executables):
            raise UserError("Niepoprawna ścieżka pliku startowego.")
        if source.get("adapter", "native") not in {"native", "native-wizard", "pinyon", "pinyon-legacy", "flatpak", "appimage", "apk"}:
            raise UserError("Nieobsługiwany adapter portu.")
        if source.get("channel", "final") not in {"final", "preview"}:
            raise UserError("Niepoprawny kanał źródła.")
        for flag in ["verified", "archived", "supported", "auto_update", "public_listing"]:
            if flag in source and not isinstance(source[flag], bool):
                raise UserError("Niepoprawna flaga źródła.")
        if not 1 <= len(source.get("name", "")) <= 150 or len(source.get("note", "")) > 4000:
            raise UserError("Niepoprawna nazwa lub opis źródła.")
        if source.get("guide") and not source["guide"].startswith("https://"):
            raise UserError("Instrukcja musi używać HTTPS.")
    for game in games:
        if not isinstance(game,dict): raise UserError('Niepoprawny wpis katalogu.')
        validate_labels(game,'technologies')
        validate_labels(game,'tags')
        if not isinstance(game.get('description',''),str) or len(game.get('description',''))>16000:
            raise UserError('Niepoprawny opis gry.')
        if not isinstance(game.get('test_notes',''),str) or len(game.get('test_notes',''))>3000:
            raise UserError('Niepoprawny opis działania gry.')
        reports=game.get('performance_reports',[])
        if not isinstance(reports,list) or len(reports)>10 or any(not isinstance(r,dict) or not isinstance(r.get('metrics'),dict) for r in reports):
            raise UserError('Niepoprawne pomiary gry.')
        if not 1 <= len(game.get("title", "")) <= 200 or game.get("platform") not in PLATFORMS:
            raise UserError("Niepoprawny wpis gry.")
        if any(ident not in seen for ident in game.get("source_ids", [])):
            raise UserError("Gra odwołuje się do brakującego źródła.")
        if game.get("cover") and not re.fullmatch(r"[a-zA-Z0-9_.-]{1,180}\.(?:png|jpg|jpeg|webp)", game["cover"]):
            raise UserError("Niepoprawna nazwa okładki.")
    return value

def entry(source, game):
    return validate_registry({"schema_version": 1, "sources": [{k:v for k,v in source.items() if k in FIELDS}],
        "featured": [{"title": game["title"], "match": game["title"], "platform": game["platform"], "rank": game.get("rank", 100), "source_ids": [source["id"]]}]})
