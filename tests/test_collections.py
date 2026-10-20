from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from recopile.service import Launcher
from recopile.storage import game_id

ROOT = Path(__file__).resolve().parents[1]


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='recopile-collections-')
        self.app = Launcher(ROOT, Path(self.tmp.name) / 'state', automatic=False)
        self.app.save_preferences({'games_dir':str(Path(self.tmp.name)/'library')})

    def tearDown(self):
        self.app.shutdown()
        self.app.media.pool.shutdown(wait=True)
        self.app.jobs.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def test_collections_reuse_first_game_without_fetching_series_artwork(self):
        with patch('recopile.media.read_media') as remote:
            collections = {c['id']:c for c in self.app.collections()}
        remote.assert_not_called()
        self.assertEqual(collections['forza-horizon']['cover_game']['id'],game_id('xbox360','Forza Horizon'))
        ratchet=collections['ratchet-and-clank']
        self.assertEqual(ratchet['cover_game']['id'],game_id('ps2','Ratchet & Clank'))
        self.assertEqual(ratchet['cover_game']['wiki_title'],'Ratchet & Clank (2002 video game)')
        ids=[c['cover_game']['id'] for c in collections.values()]
        with patch.object(self.app.media,'request') as request:
            self.app.request_media({'game_ids':ids,'covers':True})
        games=request.call_args.args[0]
        self.assertEqual({g['id'] for g in games},set(ids))
        self.assertTrue(request.call_args.kwargs['covers'])
        self.assertEqual(next(g for g in games if g['platform']=='ps2')['wiki_title'],ratchet['cover_game']['wiki_title'])

    def test_pc_install_links_to_pc_entry_and_keeps_xbox_one_separate(self):
        title='Forza Horizon 3'
        before=next(c for c in self.app.collections() if c['id']=='forza-horizon')
        pc=next(item for item in before['pc_titles'] if item['title']==title)
        self.assertIsNone(pc['game'])
        executable=Path(self.tmp.name)/'ForzaHorizon3.exe'
        executable.write_bytes(b'Local fixture; never executed')
        added=self.app.add_local_game({'title':title,'platform':'other','path':str(executable),'trusted':True,'runner':'native'})
        after=next(c for c in self.app.collections() if c['id']=='forza-horizon')
        pc=next(item for item in after['pc_titles'] if item['title']==title)
        self.assertEqual(pc['game']['id'],added['id'])
        self.assertTrue(pc['game']['install']['ready'])
        self.assertEqual(pc['game']['kind'],'native')
        self.assertEqual(pc['game']['platform'],'other')
        xbox=self.app.detail(game_id('xboxone',title))
        self.assertIsNone(xbox['install'])
        self.assertEqual(xbox['kind'],'catalog')
        self.assertEqual(pc['availability'],'delisted')

    def test_forza_contains_ports_and_pc_versions_without_inventing_a_steam_edition(self):
        collection=next(c for c in self.app.collections() if c['id']=='forza-horizon')
        titles=sorted([*collection['entries'],*collection['pc_titles']],key=lambda item:item['year'])
        self.assertEqual([item['title'] for item in titles],['Forza Horizon',*[f'Forza Horizon {n}' for n in range(2,7)]])
        self.assertTrue(all(item['game']['kind']=='recompile' for item in collection['entries']))
        fh3=next(item for item in collection['pc_titles'] if item['title']=='Forza Horizon 3')
        self.assertNotIn('steam_app_id',fh3)
        self.assertIn('xbox.com',fh3['store_url'])
        self.assertFalse(titles[1]['game']['install'])
        self.assertTrue(any(source.get('development_status')=='in_progress' for source in titles[1]['game']['sources']))

    def test_launching_both_recompilations_and_pc_copy_records_each_game_in_launching_profile(self):
        program=Path(self.tmp.name)/'inert-game'
        program.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(1.2)\n')
        program.chmod(0o755)
        ids=[game_id('xbox360','Forza Horizon'),game_id('xbox360','Forza Horizon 2')]
        for ident in ids:
            self.app.register_executable(ident,{'path':str(program),'trusted':True})
        pc=self.app.add_local_game({'title':'Forza Horizon 3','platform':'other','path':str(program),'trusted':True})
        ids.append(pc['id'])
        for ident in ids:self.app.launch(ident)
        second=self.app.profiles.create('Second player')
        self.app.profiles.switch(second['id'])
        deadline=time.monotonic()+6
        while self.app.active_processes() and time.monotonic()<deadline:time.sleep(.02)
        self.assertFalse(self.app.active_processes())
        first=self.app.profiles.summary('local')
        self.assertEqual({item['game_id'] for item in first['games']},set(ids))
        self.assertEqual(first['launches'],3)
        self.assertTrue(all(item['seconds']>=1 and item['launches']==1 and item['can_launch'] for item in first['games']))
        self.assertTrue(all(item['game_achievements']=={'status':'not_connected','unlocked':None,'total':None} for item in first['games']))
        self.assertEqual(self.app.profiles.summary()['games'],[])
        self.assertTrue(first['achievements'])
        self.assertTrue(all(badge['origin']=='launcher' for badge in first['achievements']))
        # Process completion includes the profile write, so UI refresh has no race.
        self.assertTrue(all(self.app.store.get('installs',ident)['play_seconds']>=1 for ident in ids))
