"""Consent, measured statistics, local capture and downloaded catalog metadata."""
import copy
import base64
import hashlib
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from recopile import __version__
from recopile.network import UserError
from recopile.performance import analyse_csv
from recopile.registry import validate_registry
from recopile.service import Launcher
from recopile.storage import game_id

def mango(count=200):
    stamp=0
    lines=['os,cpu,gpu,ram,kernel,driver','Fixture OS,CPU,GPU,16,6,1','fps,frametime,elapsed']
    for i in range(count):
        ms=10 if i%2==0 else 20
        stamp+=ms*1_000_000
        lines.append(f'{1000/ms},{ms},{stamp}')
    return '\n'.join(lines)+'\n'

class CSVTests(unittest.TestCase):
    def test_frame_average_uses_total_frame_time_and_mango_nanoseconds(self):
        m=analyse_csv(mango())
        self.assertEqual(m['average_fps'],66.67)
        self.assertEqual(m['one_percent_low_fps'],50)
        self.assertEqual(m['basis'],'per_frame')
        self.assertEqual(m['duration_seconds'],2.99)
        self.assertEqual(m['p99_frametime_ms'],20)

    def test_sampled_mango_does_not_claim_per_frame_lows(self):
        text='fps,frametime,elapsed\n'+''.join(f'60,16.667,{i*100000000}\n' for i in range(200))
        m=analyse_csv(text)
        self.assertEqual(m['basis'],'sampled_fps')
        self.assertIsNone(m['one_percent_low_fps'])
        self.assertEqual(m['average_fps'],60)

    def test_presentmon_requires_process_and_swapchain_selection(self):
        text='Application,ProcessID,SwapChainAddress,TimeInSeconds,MsBetweenPresents\n'
        text+='game.exe,1,0x1,0.1,10\ngame.exe,1,0x1,0.2,20\n'
        text+='other.exe,2,0x2,0.1,100\nother.exe,2,0x2,0.2,100\n'
        choices=analyse_csv(text)
        self.assertTrue(choices['selection_required'])
        self.assertEqual(len(choices['streams']),2)
        m=analyse_csv(text,stream='game.exe|1|0x1')
        self.assertEqual(m['average_fps'],66.67)
        self.assertEqual(m['samples'],2)
        with self.assertRaises(UserError):analyse_csv(text,stream='missing')

    def test_invalid_and_nonfinite_samples_never_become_fps(self):
        with self.assertRaises(UserError):analyse_csv('fps,frametime,elapsed\nNaN,16,0\n60,Inf,1\n')
        with self.assertRaises(UserError):analyse_csv('Average FPS,1% low\n123,100\n')
        with self.assertRaises(UserError):analyse_csv('fps,frametime,elapsed\n60,16,1\n')

class PerformanceAndCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='recopile-performance-test-')
        self.root=Path(self.tmp.name)
        self.app=Launcher(ROOT,self.root/'state',automatic=False)
        self.app.save_preferences({'games_dir':str(self.root/'library'),'check_updates':False})
        self.hardware={'system':'Linux','cpu':'Fixture CPU','gpu':'Fixture GPU','ram_gb':16,'driver':'1.0'}
        self.app.store.put('settings','benchmark_hardware',self.hardware)
        program=self.root/'game.py'
        program.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(.25)\n')
        program.chmod(0o755)
        self.game=self.app.add_local_game({'title':'Measurement fixture','platform':'other','path':str(program),'trusted':True,'runner':'native'})

    def tearDown(self):
        self.app.shutdown()
        self.app.media.pool.shutdown(wait=True)
        self.app.jobs.pool.shutdown(wait=True)
        self.tmp.cleanup()


    def test_app_notice_only_first_run_and_changed_version_or_license(self):
        self.assertTrue(self.app.documents.app_notice(__version__)['first_run'])
        self.app.finish_notice({'accepted':True})
        notice=self.app.documents.app_notice(__version__)
        self.assertFalse(notice['required'])
        self.assertFalse(notice['updated'])
        updated=self.app.documents.app_notice('99.0')
        self.assertTrue(updated['required'])
        self.assertTrue(updated['updated'])
        self.assertFalse(updated['first_run'])
        with patch('recopile.service.__version__','99.0'):
            with self.assertRaises(UserError):self.app.finish_notice({'accepted':False})
            self.app.finish_notice({'accepted':True})
        self.assertFalse(self.app.documents.app_notice('99.0')['required'])


    def test_capture_uses_private_config_and_leaves_game_running(self):
        wrapper=self.root/'mangohud'
        wrapper.write_text('#!/usr/bin/env python3\nimport os, pathlib, subprocess\n'
            'config=pathlib.Path(os.environ["MANGOHUD_CONFIGFILE"]).read_text()\n'
            'folder=next(l.split("=",1)[1] for l in config.splitlines() if l.startswith("output_folder="))\n'
            'pathlib.Path(folder,"capture.csv").write_text('+repr(mango())+')\n'
            'raise SystemExit(subprocess.call(__import__("sys").argv[2:]))\n')
        wrapper.chmod(0o755)
        with patch('recopile.performance.shutil.which',return_value=str(wrapper)):
            session=self.app.performance.start({'game_id':self.game['id'],'duration':1,'warmup':1})
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            saved=self.app.store.get('benchmarks',session['id'])
            if saved['status']=='complete':break
            time.sleep(.05)
        self.assertEqual(saved['status'],'complete',saved)
        self.assertEqual(saved['metrics']['average_fps'],66.67)
        config=(self.app.store.root/'benchmarks'/session['id']/'MangoHud.conf').read_text()
        self.assertIn('permit_upload=0',config)
        self.assertIn('log_interval=0',config)
        self.assertNotIn(self.game['id'],[x['id'] for x in self.app.active_processes()])

    def test_missing_recorder_does_not_launch_game_or_create_fake_results(self):
        with patch('recopile.performance.shutil.which',return_value=None):
            with self.assertRaises(UserError):self.app.performance.start({'game_id':self.game['id']})
        self.assertFalse(self.app.active_processes())
        self.assertFalse(self.app.store.list('benchmarks'))


    def test_declared_technologies_are_searchable_without_inferred_graphics_claims(self):
        result=self.app.query(q='Vulkan',limit=100)
        ratchet=next(g for g in result['games'] if g['id']==game_id('ps2','Ratchet & Clank 3'))
        self.assertIn({'id':'vulkan','label':'Vulkan'},ratchet['declared_technologies'])
        xboxone=self.app.query(q='Forza Horizon',platform='xboxone',limit=100)['games']
        azimuth=next(g for g in xboxone if g['id']==game_id('xboxone','Forza Horizon 2'))
        self.assertIn({'id':'Direct3D 12','label':'Direct3D 12'},azimuth['declared_technologies'])
        unsupported=[g for g in xboxone if g['id']!=azimuth['id']]
        self.assertTrue(all(not g['declared_technologies'] for g in unsupported))

    def test_single_runtime_catalog_sync_survives_offline_restart_without_app_onboarding(self):
        self.app.finish_notice({'accepted':True})
        original=json.loads((ROOT/'data/registry.json').read_text())
        source=next(s for s in original['sources'] if s['id']=='pinyon')
        source.update(repo='example/new-port',technologies=['vulkan'])
        featured=next(g for g in original['featured'] if 'pinyon' in g.get('source_ids',[]))
        featured.update(description='Published curated description',tags=['racing'])
        original.update(catalog_version='catalog-only-2',catalog_notes='Metadata update')
        raw=json.dumps(original).encode()
        with patch('recopile.service.fetch_json',return_value={'encoding':'base64','content':base64.b64encode(raw).decode(),'sha':'new-catalog-sha'}):
            result=self.app.sync_catalog()
        self.assertEqual(result['catalog_version'],'catalog-only-2')
        self.assertFalse(self.app.documents.app_notice(__version__)['required'])
        from recopile.storage import Store
        restarted=Store(ROOT,self.app.store.root)
        self.assertEqual(restarted.get('sources','pinyon')['repo'],'example/new-port')
        game=restarted.game(game_id(featured['platform'],featured['match']))
        self.assertEqual(game['description'],'Published curated description')
        self.assertEqual(game['tags'],['racing'])

if __name__=='__main__':unittest.main()
