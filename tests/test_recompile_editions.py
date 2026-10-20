from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from recopile.network import UserError
from recopile.service import Launcher
from recopile.storage import game_id

ROOT = Path(__file__).resolve().parents[1]


class LocalEditionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='recopile-edition-test-')
        self.root = Path(self.tmp.name)
        self.app = Launcher(ROOT, self.root/'state', automatic=False)
        self.app.save_preferences({'games_dir':str(self.root/'library')})
        self.project = self.root/'Ratchet ; own $(project)'
        (self.project/'tools').mkdir(parents=True)
        (self.project/'README.md').write_text('Local research fixture')
        (self.project/'tools/run-native.sh').write_text('#!/bin/sh\ncd "$(dirname "$0")/.."\nprintf ran > fixture-ran\n')
        binary = self.project/'build/native/ps2xRuntime/ratchet-recomp'
        binary.parent.mkdir(parents=True)
        binary.write_text('Fixture executable existence check only')
        self.ident = game_id('ps2','Ratchet & Clank 3')

    def tearDown(self):
        self.app.shutdown()
        self.app.jobs.pool.shutdown(wait=True)
        self.app.media.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def bind(self, **changes):
        return self.app.bind_project({'source_id':'ratchet3-local','trusted':True,'root':str(self.project),**changes})

    def test_local_linux_edition_launches_existing_script_without_claiming_gameplay(self):
        install = self.bind()
        self.assertEqual(install['edition'],'recopile')
        self.assertTrue(install['experimental'])
        self.assertFalse(install['ready'])
        self.assertEqual(install['local_system'],'linux')
        detail = self.app.detail(self.ident)
        self.assertEqual(detail['local_project']['root'],str(self.project))
        self.assertEqual(self.app.query(q='Ratchet & Clank 3',view='device')['total'],1)
        self.app.launch(self.ident)
        deadline = time.monotonic()+3
        while time.monotonic()<deadline and self.app.active_processes(): time.sleep(.02)
        self.assertEqual((self.project/'fixture-ran').read_text(),'ran')
        self.assertFalse(self.app.detail(self.ident)['install']['ready'])
        self.assertEqual((self.project/'README.md').read_text(),'Local research fixture')

    def test_binding_requires_trust_and_a_complete_local_project(self):
        for changes in ({'trusted':False},{'trusted':'true'},{'root':''},{'root':str(self.root)}):
            with self.subTest(changes=changes), self.assertRaises(UserError): self.bind(**changes)
        self.assertFalse(self.app.store.get('installs',self.ident))

    def test_linux_research_is_not_advertised_as_a_windows_installation(self):
        self.bind()
        with patch.object(self.app,'system_key',return_value='windows'):
            self.assertEqual(self.app.query(q='Ratchet & Clank 3',view='device')['total'],0)
            with self.assertRaises(UserError): self.bind()
