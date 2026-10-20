"""Read installed Steam apps locally; never edit Steam files or access an account.

Steam remains responsible for launching its apps, their licenses and compatibility
settings. A client handoff is deliberately not recorded as a timed game session.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path, PureWindowsPath

from .network import UserError
from .storage import game_id


_TOKENS = re.compile(r'\s+|//[^\r\n]*|"(?:\\.|[^"\\])*"|[{}]|[^\s"{}]+')
_APP_ID = re.compile(r'[1-9][0-9]{0,9}')


def parse_vdf(text):
    """Parse the bounded text KeyValues subset used by library and app manifests."""
    tokens = []
    end = 0
    for match in _TOKENS.finditer(text.lstrip('\ufeff')):
        if match.start() != end:
            raise ValueError('Invalid KeyValues text')
        end = match.end()
        token = match[0]
        if token.isspace() or token.startswith('//'):
            continue
        if token.startswith('"'):
            token = re.sub(r'\\([\\"])', r'\1', token[1:-1])
            tokens.append(('text', token))
        else:
            tokens.append((token if token in '{}' else 'text', token))
        if len(tokens) > 100000:
            raise ValueError('KeyValues file is too large')
    if end != len(text.lstrip('\ufeff')):
        raise ValueError('Incomplete KeyValues text')
    index = 0

    def block(depth=0):
        nonlocal index
        if depth > 24:
            raise ValueError('KeyValues nesting is too deep')
        result = {}
        while index < len(tokens):
            kind, key = tokens[index]
            index += 1
            if kind == '}' and depth:
                return result
            if kind != 'text' or index == len(tokens):
                raise ValueError('Invalid KeyValues key')
            kind, value = tokens[index]
            index += 1
            if kind == '{':
                value = block(depth + 1)
            elif kind != 'text':
                raise ValueError('Invalid KeyValues value')
            result[key.casefold()] = value
        if depth:
            raise ValueError('Unclosed KeyValues block')
        return result

    return block()


def read_vdf(path):
    with Path(path).open('rb') as file:
        raw = file.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('Steam manifest is too large')
    return parse_vdf(raw.decode('utf-8-sig', errors='replace'))


def library_root(path):
    root = Path(path).expanduser()
    if root.name.casefold() == 'common' and root.parent.name.casefold() == 'steamapps':
        root = root.parent.parent
    elif root.name.casefold() == 'steamapps':
        root = root.parent
    return root.resolve()


def _windows_roots():
    # These are client installation keys, never login or account keys.
    import winreg
    roots = []
    for hive, key, name in [
        (winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
        (winreg.HKEY_LOCAL_MACHINE, r'Software\Valve\Steam', 'InstallPath'),
        (winreg.HKEY_LOCAL_MACHINE, r'Software\WOW6432Node\Valve\Steam', 'InstallPath'),
    ]:
        try:
            with winreg.OpenKey(hive, key) as handle:
                roots.append(Path(winreg.QueryValueEx(handle, name)[0]))
        except OSError:
            pass
    return roots


def client_roots(home=None, system=None, environ=None):
    home = Path(home) if home else Path.home()
    system = system or ('windows' if os.name == 'nt' else 'linux')
    environ = os.environ if environ is None else environ
    if system == 'windows':
        roots = _windows_roots() if os.name == 'nt' else []
        roots.extend(Path(environ[key]) / 'Steam' for key in ('ProgramFiles(x86)', 'ProgramFiles') if environ.get(key))
        return roots
    if system != 'linux':
        return []
    return [Path(environ.get('XDG_DATA_HOME', str(home / '.local/share'))) / 'Steam',
            home / '.local/share/Steam', home / '.steam/steam', home / '.steam/root',
            home / '.steam/debian-installation',
            home / '.var/app/com.valvesoftware.Steam/.local/share/Steam']


def discover_libraries(extra=(), *, home=None, system=None, environ=None):
    """Follow registered libraries, including unavailable external drives."""
    libraries = {}
    clients = []

    def add(path, origin, client=None):
        path = Path(path).expanduser()
        if not path.is_absolute():
            return
        root = library_root(path)
        key = str(root)
        if key not in libraries:
            libraries[key] = {'path': key, 'available': (root / 'steamapps').is_dir(), 'origin': origin}
        if client and not libraries[key].get('client_root'):
            libraries[key]['client_root'] = str(client)
        if origin == 'client' and (root / 'steamapps').is_dir() and root not in clients:
            clients.append(root)

    for path in client_roots(home, system, environ):
        if (Path(path) / 'steamapps').is_dir():
            add(path, 'client', library_root(path))
    for path in extra:
        add(path, 'custom')
    for library in list(libraries.values()):
        root = Path(library['path'])
        if ((root / 'steam.exe').is_file() or (root / 'steam.sh').is_file()) and root not in clients:
            clients.append(root)
            library['client_root'] = str(root)
        for file in (root / 'steamapps/libraryfolders.vdf', root / 'config/libraryfolders.vdf'):
            if not file.is_file():
                continue
            try:
                folders = read_vdf(file).get('libraryfolders', {})
                if not isinstance(folders, dict):
                    continue
                for key, value in folders.items():
                    path = value.get('path') if isinstance(value, dict) else value if key.isdecimal() else None
                    if isinstance(path, str) and path:
                        add(path, 'steam', library.get('client_root'))
            except (OSError, ValueError):
                library['warning'] = 'Nie można odczytać listy bibliotek Steam.'
    return list(libraries.values()), clients


def client_command(clients, system=None, preferred=None):
    system = system or ('windows' if os.name == 'nt' else 'linux')
    if preferred:
        clients = [root for root in clients if str(root) == preferred]
        if not clients:
            return None
    if system == 'windows':
        for root in clients:
            exe = root / 'steam.exe'
            if exe.is_file():
                return [str(exe)]
    elif system == 'linux':
        flatpak_clients = [root for root in clients if 'com.valvesoftware.Steam' in root.parts]
        if flatpak_clients and len(flatpak_clients) == len(clients):
            flatpak = shutil.which('flatpak')
            return [flatpak, 'run', 'com.valvesoftware.Steam'] if flatpak else None
        steam = shutil.which('steam')
        if steam:
            return [steam]
        if any('com.valvesoftware.Steam' in root.parts for root in clients):
            flatpak = shutil.which('flatpak')
            if flatpak:
                return [flatpak, 'run', 'com.valvesoftware.Steam']
        for root in clients:
            exe = root / 'steam.sh'
            if exe.is_file() and os.access(exe, os.X_OK):
                return [str(exe)]
    return None


def read_app(file, root):
    match = re.fullmatch(r'appmanifest_([1-9][0-9]{0,9})\.acf', file.name)
    if not match:
        return None
    data = read_vdf(file).get('appstate', {})
    if not isinstance(data, dict) or data.get('appid') != match[1]:
        return None
    title = data.get('name', '')
    directory = data.get('installdir', '')
    if not isinstance(title, str) or not title.strip() or len(title) > 300 or not isinstance(directory, str) or not directory:
        return None
    # Runtime dependencies are apps too, but do not belong in the game library.
    if match[1] == '228980' or re.match(r'^(?:Steam Linux Runtime|Proton (?:\d|Experimental\b|Hotfix\b|Next\b))', title, re.I):
        return None
    if Path(directory).is_absolute() or PureWindowsPath(directory).drive or '..' in re.split(r'[/\\]', directory):
        return None
    common = (root / 'steamapps/common').resolve()
    installed = (common / directory).resolve()
    if not installed.is_relative_to(common) or installed == common or not installed.is_dir():
        return None
    if not int(data.get('stateflags', '0')) & 4:
        return None
    build_id = data.get('buildid', '')
    if not isinstance(build_id, str) or not re.fullmatch(r'[0-9]{0,20}', build_id):
        build_id = ''
    return {'app_id': int(match[1]), 'title': title.strip(), 'path': str(installed),
            'library': str(root), 'manifest': str(file), 'build_id': build_id}


def scan(extra=(), *, app_ids=(), **options):
    libraries, clients = discover_libraries(extra, **options)
    apps = {}
    warnings = []
    for library in libraries:
        library['games'] = 0
        if not library['available']:
            continue
        root = Path(library['path'])
        try:
            # Read only explicitly supported collection manifests. Other game
            # titles and installation details never enter this inventory.
            files = [root / 'steamapps' / f'appmanifest_{app_id}.acf'
                     for app_id in sorted(set(app_ids)) if _APP_ID.fullmatch(str(app_id))]
            for file in files:
                if not file.is_file():
                    continue
                try:
                    app = read_app(file, root)
                    if app:
                        library['games'] += 1
                        app['launch_available'] = bool(client_command(clients, options.get('system'), library.get('client_root')))
                        apps.setdefault(app['app_id'], app)
                except (OSError, ValueError, TypeError):
                    warnings.append({'path': str(file), 'message': 'Nie można odczytać manifestu Steam.'})
        except OSError:
            warnings.append({'path': str(root), 'message': 'Nie można odczytać biblioteki Steam.'})
    return {'apps': list(apps.values()), 'libraries': libraries,
            'client': client_command(clients, options.get('system')), 'warnings': warnings, 'checked_at': time.time()}


class SteamLibrary:
    def __init__(self, launcher):
        self.launcher = launcher
        self.store = launcher.store
        self.lock = threading.RLock()
        self.reconcile()

    def enabled(self):
        return self.launcher.preferences().get('steam_enabled') is True

    def collection_games(self):
        known = {}
        file = self.launcher.app_root / 'data/collections.json'
        if file.is_file():
            for collection in json.loads(file.read_text())['collections']:
                for item in collection.get('pc_titles', []):
                    if item.get('steam_app_id'):
                        known[item['steam_app_id']] = item
        return known

    def reconcile(self):
        """Retire earlier broad imports in hub metadata, preserving user files.

        Legacy generated entries are archived locally before removal. Manual
        paths and profile history stay intact, including for unrelated games.
        This migration reads the hub database only, even when discovery is off.
        """
        known = self.collection_games()
        archived = self.store.get('settings', 'steam_retired_imports', {})
        for game in self.store.steam_games():
            item = known.get(game.get('steam_app_id'))
            if self.enabled() and item and game['id'] == game_id('other', item['title']):
                continue
            old = self.store.get('installs', game['id'])
            manual = bool(game.get('external_local') or game.get('source_ids') or
                          old and (old.get('adapter') != 'steam' or old.get('local_executable')))
            if game['id'].startswith('steam-') and not manual:
                archived.setdefault(game['id'], {'game':game, 'install':old})
                self.store.put('settings', 'steam_retired_imports', archived)
                self.store.delete_game(game['id'])
            else:
                clean = {key:value for key,value in game.items() if key not in {'steam_app_id', 'steam_detected', 'steam_imported'}}
                if not manual:
                    clean['added'] = False
                self.store.save_game(clean)
            if old and old.get('adapter') == 'steam' and not old.get('local_executable'):
                self.store.delete('installs', game['id'])
        if not self.enabled():
            self.store.delete('settings', 'steam_scan')

    def require_enabled(self):
        if not self.enabled():
            raise UserError('Najpierw włącz opcjonalne wykrywanie gier z kolekcji w Steam.')

    def state(self):
        empty = {'installed': 0, 'libraries': [], 'game_ids': [], 'warnings': [], 'checked_at': None, 'client_available': False}
        state = self.store.get('settings', 'steam_scan', empty) if self.enabled() else empty
        return {**state, 'enabled':self.enabled(), 'scope':'collections'}

    def configure(self, data):
        enabled = data.get('enabled')
        if not isinstance(enabled, bool):
            raise UserError('Niepoprawna wartość ustawienia.')
        with self.lock:
            self.store.put('settings', 'preferences', {**self.launcher.preferences(), 'steam_enabled':enabled})
            self.reconcile()
            return self.scan() if enabled else self.state()

    def scan(self):
        with self.lock:
            self.require_enabled()
            known = self.collection_games()
            inventory = scan(self.launcher.preferences().get('steam_libraries', []), app_ids=known, system=self.launcher.system_key())
            seen = []
            added = 0
            for app in inventory['apps']:
                item = known.get(app['app_id'])
                if not item:
                    continue
                title = item['title']
                ident = game_id('other', title)
                game = self.store.game(ident)
                if game is None:
                    game = {'id': ident, 'title': title, 'platform': 'other', 'kind': 'native',
                            'source_ids': [], 'variants': [], 'added': True, 'steam_imported':True}
                    if item.get('year'):
                        game['year'] = item['year']
                    added += 1
                self.store.save_game({**game, 'steam_app_id': app['app_id'], 'steam_detected': True, 'added':True})
                seen.append(ident)
                old = self.store.get('installs', ident)
                # A deliberately configured program/port always takes precedence.
                if old and (old.get('adapter') != 'steam' or old.get('local_executable')):
                    continue
                install = old or {'id': ident, **self.launcher.game_location(ident, title, 'other'), 'installed_at': time.time(), 'play_seconds': 0}
                # Only the hub database is written. No manifests, folders or save
                # configuration are created inside the actual Steam library.
                self.store.put('installs', ident, {**install, 'adapter': 'steam', 'ready': app['launch_available'],
                    'steam_app_id': app['app_id'], 'steam_install_dir': app['path'], 'steam_library': app['library'],
                    'steam_manifest': app['manifest'], 'version': app['build_id'], 'session_tracking': 'not_connected'})
            previous = set(self.state().get('game_ids', [])) | {i['id'] for i in self.store.list('installs') if i.get('adapter') == 'steam'}
            for ident in previous - set(seen):
                game = self.store.game(ident)
                if game:
                    self.store.save_game({**game, 'steam_detected': False})
                old = self.store.get('installs', ident)
                if old and old.get('adapter') == 'steam' and not old.get('local_executable'):
                    self.store.delete('installs', ident)
            state = {k: v for k, v in inventory.items() if k not in {'apps', 'client'}}
            state.update(installed=len(inventory['apps']), added=added, game_ids=seen, client_available=bool(inventory['client']))
            self.store.put('settings', 'steam_scan', state)
            return self.state()

    def library(self, data):
        self.require_enabled()
        path = data.get('path')
        if not isinstance(path, str) or not path.strip() or len(path) > 4096 or not Path(path).expanduser().is_absolute():
            raise UserError('Wskaż folder biblioteki Steam.')
        root = library_root(path)
        if data.get('remove') is not True and not (root / 'steamapps').is_dir():
            raise UserError('Wskaż folder Steam lub SteamLibrary zawierający steamapps.')
        with self.lock:
            prefs = self.launcher.preferences()
            paths = prefs.get('steam_libraries', [])
            paths = [p for p in paths if p != str(root)] if data.get('remove') is True else list(dict.fromkeys([*paths, str(root)]))
            if len(paths) > 50:
                raise UserError('Można wskazać maksymalnie 50 dodatkowych bibliotek Steam.')
            self.store.put('settings', 'preferences', {**prefs, 'steam_libraries': paths})
            return self.scan()

    def launch(self, ident, install):
        self.require_enabled()
        if self.launcher.system_key() not in {'linux', 'windows'}:
            raise UserError('Uruchamianie przez Steam jest dostępne na Linuxie i Windowsie.')
        app_id = str(install.get('steam_app_id', ''))
        if not _APP_ID.fullmatch(app_id):
            raise UserError('Niepoprawny identyfikator gry Steam.')
        item = self.collection_games().get(int(app_id))
        if not item or ident != game_id('other', item['title']):
            raise UserError('Wykrywanie Steam obejmuje tylko gry z kolekcji RE:COPILE.')
        try:
            app = read_app(Path(install['steam_manifest']), Path(install['steam_library']))
        except (OSError, ValueError, TypeError):
            app = None
        if not app or str(app['app_id']) != app_id:
            raise UserError('Instalacja Steam jest niedostępna. Podłącz dysk i ponownie przeskanuj biblioteki.')
        libraries, clients = discover_libraries(self.launcher.preferences().get('steam_libraries', []), system=self.launcher.system_key())
        library = next((item for item in libraries if item['path'] == install['steam_library']), {})
        command = client_command(clients, self.launcher.system_key(), library.get('client_root'))
        if not command:
            raise UserError('Nie znaleziono klienta Steam. Zainstaluj Steam i ponownie przeskanuj biblioteki.')
        log_dir = self.store.root / 'logs'
        log_dir.mkdir(exist_ok=True)
        log = (log_dir / f'steam-{app_id}-{int(time.time())}.log').open('w')
        try:
            process = subprocess.Popen([*command, '-applaunch', app_id], cwd=self.launcher.app_root,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except Exception:
            log.close()
            raise

        def reap():
            try:
                process.wait()
            finally:
                log.close()
        threading.Thread(target=reap, daemon=True, name='steam-handoff').start()
        # The forwarding process can exit immediately or remain for the whole
        # client lifetime. Neither is evidence of the game's duration.
        return {'ok': True, 'handoff': 'steam', 'pid': process.pid, 'session_tracking': 'not_connected'}
