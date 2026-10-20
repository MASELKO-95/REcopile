from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from recopile.network import UserError
from recopile.service import Launcher

ROOT = Path(__file__).resolve().parents[1]


class ModLicenseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='recopile-mod-consent-')
        self.root = Path(self.tmp.name)
        self.app = Launcher(ROOT,self.root/'state',automatic=False)
        self.app.save_preferences({'games_dir':str(self.root/'library')})
        program=self.root/'game.exe'
        program.write_bytes(b'Fixture program; never executed')
        self.game=self.app.add_local_game({'title':'License test game','platform':'other',
            'path':str(program),'trusted':True,'runner':'native'})

    def tearDown(self):
        self.app.shutdown()
        self.app.media.pool.shutdown(wait=True)
        self.app.jobs.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def package(self, license_text='Fixture license terms'):
        payload=b'Fixture mod data'
        manifest={'schema_version':1,'id':'license-fixture','name':'Fixture mod','author':'Test',
            'version':'1','game_id':self.game['id'],'supported_versions':['local'],
            'systems':['linux','windows'],'license':'LicenseRef-Fixture','files':[
                {'source':'payload/data.txt','target':'data.txt','sha256':hashlib.sha256(payload).hexdigest()}]}
        path=self.root/'mod.zip'
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('manifest.json',json.dumps(manifest))
            archive.writestr('README.md','Fixture instructions')
            archive.writestr('LICENSE',license_text)
            archive.writestr('payload/data.txt',payload)
        return path,self.app.workshop.inspect(path)

    def test_mod_requires_separate_acceptance_of_the_actual_license(self):
        path,review=self.package()
        for consent in ({},{'license_accepted':False},
                        {'license_accepted':True,'license_hash':'old-license'}):
            with self.subTest(consent=consent),self.assertRaises(UserError):
                self.app.workshop.install(path,review['fingerprint'],trusted=True,**consent)
        self.assertFalse(self.app.store.list('mods'))
        installed=self.app.workshop.install(path,review['fingerprint'],trusted=True,
            license_accepted=True,license_hash=review['license_hash'])
        self.assertTrue(installed['license_accepted'])
        self.assertEqual(installed['license_hash'],review['license_hash'])
        self.assertFalse(installed['active'])
        self.assertEqual((Path(installed['root'])/'LICENSE').read_text(),'Fixture license terms')

    def test_blank_mod_license_cannot_be_accepted(self):
        path,review=self.package('  ')
        with self.assertRaises(UserError):
            self.app.workshop.install(path,review['fingerprint'],trusted=True,
                license_accepted=True,license_hash=review['license_hash'])
        self.assertFalse(self.app.store.list('mods'))
