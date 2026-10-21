from pathlib import Path
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from recopile.network import UserError
from recopile.service import Launcher
from recopile.storage import game_id

ROOT = Path(__file__).resolve().parents[1]


class LaunchOptionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='recopile-launch-choice-')
        self.root = Path(self.temp.name)
        self.app = Launcher(ROOT, self.root / 'state', automatic=False, scan_steam=False)
        self.app.save_preferences({'games_dir': str(self.root / 'library')})
        self.ident = game_id('xbox360', 'Forza Horizon')
        self.source = self.root / 'pinyon'
        (self.source / 'tools').mkdir(parents=True)
        (self.source / 'tools/pinyon.py').write_text('# synthetic upstream CLI marker\n')
        (self.source / '.local/game/base').mkdir(parents=True)
        (self.source / '.local/game/base/default.xex').write_text('synthetic input marker')
        self.output = self.root / 'observed.json'
        code = ('#!' + sys.executable + '\nimport json, os, sys\nfrom pathlib import Path\n'
                'Path(' + repr(str(self.output)) + ').write_text(json.dumps({"args":sys.argv[1:],'
                '"environment":{key:value for key,value in os.environ.items() '
                'if key.startswith("PINYON_SHIFT_")}}))\n')
        self.game = self.root / 'game'
        self.game.write_text(code)
        self.game.chmod(0o755)
        self.gui = self.source / '.local/recopile-launcher/PinyonShiftLauncher'
        self.gui.parent.mkdir(parents=True)
        self.gui.write_text(code)
        self.gui.chmod(0o755)
        self.install = {'id': self.ident, **self.app.game_location(self.ident, 'Forza Horizon', 'xbox360'),
                        'source_id': 'pinyon', 'engine_root': str(self.source),
                        'local_executable': str(self.game), 'local_system': 'linux',
                        'ready': True, 'pinyon_state_root': str(self.root / 'existing-state')}
        self.app.save_install(self.ident, self.install)

    def tearDown(self):
        self.wait()
        self.app.shutdown()
        self.app.jobs.pool.shutdown(wait=True)
        self.app.media.pool.shutdown(wait=True)
        self.temp.cleanup()

    def wait(self):
        deadline = time.monotonic() + 5
        while self.ident in self.app.running and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertNotIn(self.ident, self.app.running)

    def test_first_play_asks_without_spawning_or_recording_a_session(self):
        result = self.app.launch(self.ident)
        self.assertTrue(result['launch_choice_required'])
        self.assertTrue(result['launcher_available'])
        self.assertFalse(self.output.exists())
        self.assertEqual(self.app.active_processes(), [])

    def test_original_gui_uses_existing_source_state_and_game_and_no_game_arguments(self):
        self.app.store.put('settings', 'launch:'+self.ident, {'arguments':['--game-only']})
        with patch.object(self.app.profiles, 'record') as recorded:
            result = self.app.launch(self.ident, launch_mode='launcher')
            self.assertTrue(result['ok'])
            self.wait()
            recorded.assert_not_called()
        observed = json.loads(self.output.read_text())
        self.assertEqual(observed['args'], [])
        env = observed['environment']
        self.assertEqual(env['PINYON_SHIFT_SOURCE_ROOT'], str(self.source))
        self.assertEqual(env['PINYON_SHIFT_STATE_ROOT'], self.install['pinyon_state_root'])
        self.assertEqual(env['PINYON_SHIFT_GAME_ROOT'], str(self.source / '.local/game/base'))
        self.assertEqual(env['PINYON_SHIFT_UPDATE_CHECK'], '0')
        self.assertEqual(self.app.store.get('installs', self.ident)['local_executable'], str(self.game))

    def test_direct_game_keeps_arguments_and_records_play(self):
        # Avoid querying a synthetic CLI: launch arguments are independent of config reads.
        self.app.store.put('settings','launch:'+self.ident,{'arguments':['--literal=a; b']})
        with patch.object(self.app.profiles, 'record') as recorded:
            self.app.launch(self.ident, launch_mode='game')
            self.wait()
            recorded.assert_called_once()
        self.assertEqual(json.loads(self.output.read_text())['args'], ['--literal=a; b'])

    def test_remembered_choice_can_be_changed_and_forgotten(self):
        self.app.launch(self.ident, launch_mode='game', remember=True)
        self.wait()
        self.assertEqual(self.app.detail(self.ident)['launch_options']['preferred'], 'game')
        self.assertTrue(self.app.launch(self.ident, launch_mode='ask')['launch_choice_required'])
        self.app.launch(self.ident, launch_mode='launcher', remember=False)
        self.wait()
        self.assertTrue(self.app.launch(self.ident)['launch_choice_required'])

    def test_missing_launcher_recovers_a_remembered_gui_choice_and_does_not_remember_failure(self):
        self.gui.unlink()
        self.app.store.put('settings','launch-choice:'+self.ident,{'mode':'launcher'})
        result = self.app.launch(self.ident)
        self.assertTrue(result['launch_choice_required'])
        self.assertFalse(result['launcher_available'])
        with self.assertRaises(UserError):
            self.app.launch(self.ident, launch_mode='launcher', remember=True)
        self.assertFalse(self.output.exists())

    def test_invalid_selection_and_remember_flag_are_rejected(self):
        for kwargs in ({'launch_mode':'shell'}, {'launch_mode':[]}, {'launch_mode':'game','remember':'yes'}):
            with self.assertRaises(UserError):
                self.app.launch(self.ident, **kwargs)
        self.assertFalse(self.output.exists())

    def test_other_games_keep_direct_play(self):
        self.app.save_install(self.ident, {**self.install, 'source_id':'other'})
        self.assertIsNone(self.app.detail(self.ident)['launch_options'])
        self.assertTrue(self.app.launch(self.ident)['ok'])
        self.wait()


if __name__ == '__main__':
    unittest.main()
