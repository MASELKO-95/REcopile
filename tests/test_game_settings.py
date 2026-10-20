from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from recopile.network import UserError
from recopile.service import Launcher
from recopile.storage import game_id

ROOT=Path(__file__).resolve().parents[1]


class GameSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='recopile-settings-')
        self.root=Path(self.temp.name)
        self.app=Launcher(ROOT,self.root/'state',automatic=False)
        self.ident=game_id('xbox360','Forza Horizon 2')
        self.app.save_preferences({'games_dir':str(self.root/'library')})
        self.script=self.root/'game.py'
        self.script.write_text('#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nPath(__file__).with_suffix(".json").write_text(json.dumps(sys.argv[1:]))\n')
        self.script.chmod(0o755)
        self.install={'id':self.ident,**self.app.game_location(self.ident,'Forza Horizon 2','xbox360'),
                      'local_executable':str(self.script),'ready':True,'local_system':'linux','runner':'native'}
        self.app.save_install(self.ident,self.install)

    def tearDown(self):
        self.app.shutdown();self.app.jobs.pool.shutdown(wait=True);self.app.media.pool.shutdown(wait=True)
        self.temp.cleanup()

    def request(self,operation='get',**data):
        return self.app.game_settings.request(self.ident,{'operation':operation,**data})

    def test_settings_are_optional_and_launch_arguments_remain_literal(self):
        info=self.app.detail(self.ident)['game_settings']
        self.assertTrue(info['optional'])
        self.assertEqual(self.request()['fields'],[])
        self.assertFalse(self.app.running)
        args=['--name=some game','$(touch '+str(self.root/'bad')+')','; echo no-shell']
        self.request('apply',launch={'arguments':args})
        self.app.launch(self.ident)
        deadline=time.monotonic()+5
        while self.ident in self.app.running and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(json.loads(self.script.with_suffix('.json').read_text()),args)
        self.assertFalse((self.root/'bad').exists())

    def test_invalid_launch_options_and_running_game_do_not_change_settings(self):
        with self.assertRaises(UserError):self.request('apply',launch={'arguments':'--wrong'})
        with self.assertRaises(UserError):self.request('apply',launch={'arguments':['a\0b']})
        self.assertIsNone(self.app.store.get('settings','launch:'+self.ident))
        self.app.running[self.ident]={'process':None}
        try:
            with self.assertRaises(UserError):self.request('apply',launch={'arguments':['--change']})
            self.assertEqual(self.request()['launch']['arguments'],[])
        finally:self.app.running.clear()

    def test_fh2_exposes_only_its_actual_runtime_options_and_keeps_other_games_separate(self):
        install={**self.install,'source_id':'fh2-recomp-maselko','engine_root':str(self.root)}
        self.app.save_install(self.ident,install)
        self.assertEqual(self.request()['driver'],'fh2')
        with self.assertRaises(UserError):self.request('apply',values={'output_scaling':'fsr2'})
        with self.assertRaises(UserError):self.request('apply',values={'resolution_scale':True})
        self.request('apply',values={'resolution_scale':2,'vsync':False,'anisotropy':16})
        args=self.app.game_settings.arguments(self.ident,install)
        self.assertIn('--draw_resolution_scale_x=2',args)
        self.assertIn('--draw_resolution_scale_y=2',args)
        self.assertIn('--anisotropic_override=5',args)
        self.assertIn('--vsync=false',args)
        other=game_id('xbox360','Forza Horizon')
        self.assertEqual(self.app.game_settings.arguments(other,self.install),[])
        self.request('reset')
        self.assertEqual(self.request()['settings']['resolution_scale'],1)

    def test_settings_compatibility_selection_is_used_without_replacing_install(self):
        install={**self.install,'local_system':'windows','runner':'proton','proton_path':'old'}
        self.app.save_install(self.ident,install)
        with patch.object(self.app,'system_key',return_value='linux'):
            self.request('apply',launch={'arguments':[],'runner':'wine','proton_path':''})
            selected=self.app.game_settings.launch_install(self.ident,install)
        self.assertEqual(selected['runner'],'wine')
        self.assertEqual(self.app.store.get('installs',self.ident)['runner'],'proton')


if __name__=='__main__':unittest.main()
