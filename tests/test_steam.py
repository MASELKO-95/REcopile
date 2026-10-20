from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from recopile import steam
from recopile.network import UserError
from recopile.service import Launcher
from recopile.storage import game_id

ROOT = Path(__file__).resolve().parents[1]


def vdf(value):
    return '\n'.join(json.dumps(str(key)) + ' ' + ('{\n' + vdf(item) + '\n}' if isinstance(item, dict) else json.dumps(str(item), ensure_ascii=False)) for key, item in value.items())


def manifest(root, app_id, title, directory=None, flags=4):
    directory = title if directory is None else directory
    folder = root / 'steamapps'
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / f'appmanifest_{app_id}.acf'
    file.write_text(vdf({'AppState': {'appid': app_id, 'name': title, 'installdir': directory, 'StateFlags': flags, 'buildid': '123'}}))
    if directory and directory != '..':
        (folder / 'common' / directory).mkdir(parents=True, exist_ok=True)
    return file


FH5 = game_id('other', 'Forza Horizon 5')
RIFT = game_id('other', 'Ratchet & Clank: Rift Apart')


class SteamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='recopile-steam-')
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.client = self.home / '.local/share/Steam'
        self.library = self.root / 'Second Steam Library'
        self.offline = self.root / 'Offline Drive/SteamLibrary'
        (self.client / 'steamapps').mkdir(parents=True)
        (self.library / 'steamapps').mkdir(parents=True)
        self.folders = self.client / 'steamapps/libraryfolders.vdf'
        self.folders.write_text(vdf({'libraryfolders': {'0': {'path': str(self.client)}, '1': {'path': str(self.library)}, '2': {'path': str(self.offline)}}}))
        self.roots = patch('recopile.steam.client_roots', return_value=[self.client, self.client])
        self.roots.start()
        self.command = patch('recopile.steam.client_command', return_value=['/fixture/steam'])
        self.client_mock = self.command.start()
        self.app = Launcher(ROOT, self.root / 'state', automatic=False)
        self.app.save_preferences({'games_dir': str(self.root / 'RecopileLibrary')})

    def tearDown(self):
        self.app.shutdown()
        self.app.media.pool.shutdown(wait=True)
        self.app.jobs.pool.shutdown(wait=True)
        self.command.stop()
        self.roots.stop()
        self.tmp.cleanup()

    def enable(self):
        return self.app.steam.configure({'enabled': True})

    def test_disabled_by_default_even_with_startup_scan_requested(self):
        manifest(self.library, 1551360, 'Forza Horizon 5')
        with patch('recopile.steam.scan') as inventory:
            other = Launcher(ROOT, self.root / 'new-state', automatic=False, scan_steam=True)
            try:
                self.assertFalse(other.preferences()['steam_enabled'])
                self.assertEqual(other.steam.state()['installed'], 0)
                self.assertFalse(other.steam.state()['enabled'])
                with self.assertRaises(UserError):
                    other.steam.scan()
                with self.assertRaises(UserError):
                    other.steam.library({'path': str(self.library)})
            finally:
                other.shutdown()
        inventory.assert_not_called()
        self.app.save_preferences({'steam_enabled': True})
        self.assertFalse(self.app.steam.enabled())
        with self.assertRaises(UserError):
            self.app.steam.configure({'enabled': 'true'})

    def test_keyvalues_comments_bom_escapes_and_malformed_input(self):
        text = '\ufeff// comment\n' + vdf({'LibraryFolders': {'1': {'path': 'D:\\SteamLibrary'}, '2': '/disk/SteamLibrary'}})
        self.assertEqual(steam.parse_vdf(text)['libraryfolders']['1']['path'], 'D:\\SteamLibrary')
        self.assertEqual(steam.parse_vdf(text)['libraryfolders']['2'], '/disk/SteamLibrary')
        for invalid in ['"key" {', '"key" "unclosed', '}']:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                steam.parse_vdf(invalid)

    def test_selected_manifests_modern_legacy_multiple_drives_duplicates_and_runtime_filter(self):
        manifest(self.client, 1551360, 'Forza Horizon 5')
        manifest(self.library, 1551360, 'Forza Horizon 5')
        manifest(self.client, 70, 'Half-Life')
        manifest(self.client, 2805730, 'Proton 9.0')
        manifest(self.client, 1070560, 'Steam Linux Runtime 1.0 (scout)')
        manifest(self.client, 228980, 'Steamworks Common Redistributables')
        ids = [1551360, 2805730, 1070560, 228980]
        inventory = steam.scan(app_ids=ids)
        self.assertEqual([app['app_id'] for app in inventory['apps']], [1551360])
        self.assertEqual(len(inventory['libraries']), 3)
        self.assertFalse(next(item for item in inventory['libraries'] if item['path'] == str(self.offline))['available'])
        self.folders.write_text(vdf({'LibraryFolders': {'1': str(self.library)}}))
        self.assertEqual([app['app_id'] for app in steam.scan(app_ids=ids)['apps']], [1551360])
        self.assertEqual(steam.scan()['apps'], [])

    def test_partial_missing_mismatched_and_escaping_manifests_are_not_imported(self):
        manifest(self.library, 1, 'Downloading', flags=1024)
        missing = manifest(self.library, 2, 'Missing')
        (self.library / 'steamapps/common/Missing').rmdir()
        manifest(self.library, 3, 'Traversal', '..')
        mismatch = manifest(self.library, 4, 'Wrong ID')
        mismatch.write_text(mismatch.read_text().replace('"appid" "4"', '"appid" "5"'))
        (self.library / 'steamapps/appmanifest_6.acf').write_text('"AppState" {')
        manifest(self.library, 7, 'Valid game')
        inventory = steam.scan(app_ids=range(1, 8))
        self.assertEqual([app['app_id'] for app in inventory['apps']], [7])
        self.assertEqual(len(inventory['warnings']), 1)
        self.assertTrue(missing.is_file())

    def test_opt_in_reads_only_collection_manifests_and_links_only_pc_editions(self):
        manifest(self.library, 1551360, 'Steam title for FH5')
        manifest(self.library, 1895880, 'Ratchet & Clank: Rift Apart')
        unrelated = manifest(self.library, 70, 'Half-Life')
        unrelated.write_text('Malformed unrelated manifest must not be read')
        before = {path.relative_to(self.library): path.read_bytes() for path in self.library.rglob('*') if path.is_file()}
        with patch('recopile.media.read_media') as media, patch('recopile.steam.subprocess.Popen') as execute, patch('recopile.steam.read_app', wraps=steam.read_app) as read:
            result = self.enable()
            again = self.app.steam.scan()
        media.assert_not_called()
        execute.assert_not_called()
        self.assertEqual({call.args[0].name for call in read.call_args_list}, {'appmanifest_1551360.acf', 'appmanifest_1895880.acf'})
        self.assertEqual(result['installed'], 2)
        self.assertTrue(result['enabled'])
        self.assertEqual(result['scope'], 'collections')
        self.assertEqual(result['added'], 2)
        self.assertEqual(again['added'], 0)
        self.assertEqual(result['warnings'], [])
        self.assertIsNone(self.app.store.game('steam-70'))
        self.assertEqual(self.app.store.stats()['installed'], 2)
        self.assertEqual(before, {path.relative_to(self.library): path.read_bytes() for path in self.library.rglob('*') if path.is_file()})
        collection = next(c for c in self.app.collections() if c['id'] == 'forza-horizon')
        game = next(item['game'] for item in collection['pc_titles'] if item.get('steam_app_id') == 1551360)
        self.assertEqual(game['id'], FH5)
        self.assertEqual(game['title'], 'Forza Horizon 5')
        self.assertEqual(game['install']['adapter'], 'steam')
        self.assertTrue(game['install']['ready'])
        self.assertEqual(game['device_options'][0]['via'], 'steam')
        self.assertIsNone(self.app.detail(game_id('xboxone', 'Forza Horizon 5'))['install'])
        self.assertIn(FH5, {g['id'] for g in self.app.query(view='library')['games']})
        self.assertIn(FH5, {g['id'] for g in self.app.query(view='device')['games']})

    def test_missing_drive_removes_automatic_install_and_retains_history(self):
        file = manifest(self.library, 1551360, 'Forza Horizon 5')
        self.enable()
        self.app.profiles.record('local', self.app.require_game(FH5), 120, 0)
        file.unlink()
        self.app.steam.scan()
        self.assertIsNone(self.app.store.get('installs', FH5))
        self.assertFalse(self.app.require_game(FH5)['steam_detected'])
        self.assertEqual(self.app.profiles.summary()['games'][0]['seconds'], 120)
        manifest(self.library, 1551360, 'Forza Horizon 5')
        self.app.steam.scan()
        self.assertTrue(self.app.store.get('installs', FH5)['ready'])

    def test_explicit_local_configuration_survives_scans_and_disabling(self):
        manifest(self.library, 1551360, 'Forza Horizon 5')
        program = self.root / 'inert-program'
        program.write_text('#!/bin/sh\nexit 0\n')
        program.chmod(0o755)
        local = self.app.add_local_game({'title': 'Forza Horizon 5', 'platform': 'other', 'path': str(program), 'trusted': True})
        before = local['install']
        self.enable()
        self.assertEqual(self.app.detail(FH5)['install'], before)
        self.app.steam.configure({'enabled': False})
        self.assertEqual(self.app.detail(FH5)['install'], before)
        self.assertTrue(self.app.require_game(FH5)['added'])

    def test_attaching_program_to_imported_game_survives_disabling(self):
        manifest(self.library, 1551360, 'Forza Horizon 5')
        self.enable()
        program = self.root / 'inert-game'
        program.write_text('#!/bin/sh\nexit 0\n')
        program.chmod(0o755)
        self.app.register_executable(FH5, {'path': str(program), 'trusted': True})
        self.app.steam.configure({'enabled': False})
        install = self.app.detail(FH5)['install']
        self.assertTrue(install['ready'])
        self.assertEqual(install['local_executable'], str(program))

    def test_unrelated_same_title_port_is_not_imported_or_modified(self):
        title = 'My PC port'
        ident = game_id('other', title)
        original = {'id': ident, 'title': title, 'platform': 'other', 'kind': 'recompile', 'source_ids': ['pinyon'], 'added':False}
        self.app.store.save_game(original)
        manifest(self.library, 123, title)
        self.enable()
        self.assertIsNone(self.app.store.game('steam-123'))
        self.assertEqual(self.app.require_game(ident), original)

    def test_custom_library_remains_collection_only_and_can_be_forgotten(self):
        extra = self.root / 'Custom library'
        manifest(extra, 1895880, 'Rift Apart')
        manifest(extra, 70, 'Unrelated game')
        self.enable()
        result = self.app.steam.library({'path': str(extra / 'steamapps/common')})
        self.assertEqual(self.app.preferences()['steam_libraries'], [str(extra)])
        self.assertEqual(result['installed'], 1)
        self.assertIsNone(self.app.store.game('steam-70'))
        self.app.steam.library({'path': str(extra / 'steamapps'), 'remove': True})
        self.assertEqual(self.app.steam.state()['installed'], 0)
        self.assertTrue((extra / 'steamapps/appmanifest_1895880.acf').is_file())
        with self.assertRaises(UserError):
            self.app.steam.library({'path': str(self.root)})
        with self.assertRaises(UserError):
            self.app.steam.library({'path': 'relative'})

    def test_launch_is_steam_handoff_without_fabricated_session(self):
        file = manifest(self.library, 1551360, 'Forza Horizon 5')
        self.enable()
        process = Mock(pid=8765)
        process.wait.return_value = 0
        with patch('recopile.steam.subprocess.Popen', return_value=process) as execute:
            result = self.app.launch(FH5)
        self.assertEqual(execute.call_args.args[0], ['/fixture/steam', '-applaunch', '1551360'])
        self.assertEqual(result['handoff'], 'steam')
        self.assertEqual(result['session_tracking'], 'not_connected')
        self.assertEqual(self.app.active_processes(), [])
        self.assertEqual(self.app.profiles.summary()['launches'], 0)
        file.unlink()
        with patch('recopile.steam.subprocess.Popen') as execute, self.assertRaises(UserError):
            self.app.launch(FH5)
        execute.assert_not_called()

    def test_client_absent_keeps_discovery_but_disables_play(self):
        manifest(self.library, 1551360, 'Forza Horizon 5')
        self.client_mock.return_value = None
        result = self.enable()
        self.assertEqual(result['installed'], 1)
        self.assertFalse(result['client_available'])
        self.assertFalse(self.app.detail(FH5)['install']['ready'])
        with self.assertRaises(UserError):
            self.app.launch(FH5)

    def test_opt_in_is_remembered_across_startup_without_auto_updates(self):
        manifest(self.library, 1551360, 'Forza Horizon 5')
        self.enable()
        self.app.save_preferences({'steam_enabled': False})
        self.assertTrue(self.app.steam.enabled())
        other = Launcher(ROOT, self.root / 'state', automatic=False, scan_steam=True)
        try:
            self.assertTrue(other.steam.state()['enabled'])
            self.assertEqual(other.steam.state()['installed'], 1)
        finally:
            other.shutdown()

    def test_disabling_removes_automatic_bindings_and_blocks_scans_without_file_reads(self):
        file = manifest(self.library, 1551360, 'Forza Horizon 5')
        self.enable()
        self.app.profiles.record('local', self.app.require_game(FH5), 120, 0)
        with patch('recopile.steam.scan') as inventory:
            state = self.app.steam.configure({'enabled': False})
            with self.assertRaises(UserError):
                self.app.steam.scan()
        inventory.assert_not_called()
        self.assertFalse(state['enabled'])
        self.assertEqual(state['libraries'], [])
        self.assertEqual(state['installed'], 0)
        self.assertIsNone(self.app.store.get('installs', FH5))
        self.assertFalse(self.app.require_game(FH5)['added'])
        self.assertEqual(self.app.profiles.summary()['games'][0]['seconds'], 120)
        self.assertTrue(file.is_file())

    def test_legacy_broad_imports_are_archived_while_history_and_manual_paths_survive(self):
        game = {'id':'steam-70', 'title':'Half-Life', 'platform':'other', 'kind':'native', 'source_ids':[], 'added':True, 'steam_app_id':70, 'steam_detected':True}
        self.app.store.save_game(game)
        install = {'id':game['id'], 'adapter':'steam', 'ready':True, 'steam_app_id':70}
        self.app.store.put('installs', game['id'], install)
        self.app.profiles.record('local', game, 120, 0)
        self.app.steam.reconcile()
        self.assertIsNone(self.app.store.game(game['id']))
        self.assertIsNone(self.app.store.get('installs', game['id']))
        self.assertEqual(self.app.store.get('settings', 'steam_retired_imports')[game['id']]['install'], install)
        history = self.app.profiles.summary()['games'][0]
        self.assertEqual(history['seconds'], 120)
        self.assertEqual(history['title'], 'Half-Life')
        self.assertFalse(history['game_available'])
        self.assertFalse(history['can_launch'])
        # An unrelated title deliberately connected by the user is preserved.
        self.app.store.save_game(game)
        self.app.store.put('installs', game['id'], {**install, 'local_executable':'/fixture/user-program'})
        self.app.steam.reconcile()
        self.assertTrue(self.app.require_game(game['id'])['added'])
        self.assertEqual(self.app.store.get('installs', game['id'])['local_executable'], '/fixture/user-program')

    def test_windows_program_files_and_flatpak_roots_and_client_commands(self):
        self.roots.stop()
        self.command.stop()
        windows = self.root / 'Program Files (x86)/Steam'
        manifest(windows, 70, 'Half-Life')
        (windows / 'steam.exe').write_bytes(b'MZ fixture, never executed')
        libraries, clients = steam.discover_libraries(system='windows', environ={'ProgramFiles(x86)': str(windows.parent)})
        self.assertEqual([item['path'] for item in libraries], [str(windows)])
        self.assertEqual(steam.client_command(clients, 'windows'), [str(windows / 'steam.exe')])
        flatpak = self.home / '.var/app/com.valvesoftware.Steam/.local/share/Steam'
        (flatpak / 'steamapps').mkdir(parents=True)
        libraries, clients = steam.discover_libraries(home=self.home, system='linux', environ={})
        self.assertIn(str(flatpak), [item['path'] for item in libraries])
        with patch('recopile.steam.shutil.which', side_effect=lambda name: '/usr/bin/' + name):
            self.assertEqual(steam.client_command(clients, 'linux', str(flatpak)), ['/usr/bin/flatpak', 'run', 'com.valvesoftware.Steam'])
            self.assertEqual(steam.client_command(clients, 'linux', str(self.client)), ['/usr/bin/steam'])
        self.roots.start()
        self.command.start()


if __name__ == '__main__':
    unittest.main()
