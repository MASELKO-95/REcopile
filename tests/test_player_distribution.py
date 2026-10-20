"""A player build has catalog readers and local sources, without owner publishing."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from recopile.network import UserError
from recopile.registry import validate_registry
from recopile.server import create_server
from recopile.service import Launcher
from recopile.technologies import declared,validate_labels

ROOT=Path(__file__).resolve().parents[1]

class PlayerDistributionTests(unittest.TestCase):
    def test_custom_labels_are_readable_without_a_preset(self):
        value={'technologies':['vulkan','FSR 3.1','Moja technologia'],'tags':['Mój własny tag','Otwarty świat']}
        validate_labels(value,'technologies');validate_labels(value,'tags')
        self.assertEqual([t['label'] for t in declared(value,[])],['Vulkan','FSR 3.1','Moja technologia'])
        for labels in [['x\ny'],[' label '],['A','a'],['x'*61]]:
            with self.assertRaises(UserError):validate_labels({'tags':labels},'tags')

    def test_player_api_has_no_owner_routes_even_with_legacy_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state';app=Launcher(ROOT,state,automatic=False)
            app.store.put('settings','preferences',{**app.preferences(),'publisher_mode':True})
            app.shutdown()
            app=Launcher(ROOT,state,automatic=False)
            self.assertFalse(hasattr(app,'publisher'))
            self.assertNotIn('publisher_mode',app.bootstrap()['settings'])
            self.assertNotIn('publisher_mode',app.save_preferences({'publisher_mode':True}))
            before=(ROOT/'data/registry.json').read_bytes()
            with self.assertRaises(UserError):app.add_source({'publish_catalog':True})
            self.assertEqual(before,(ROOT/'data/registry.json').read_bytes())
            server=create_server(app,0);threading.Thread(target=server.serve_forever,daemon=True).start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base+'/api/bootstrap') as response:token=json.load(response)['token']
                for path in ('/api/publisher','/api/publisher/games','/api/publisher/download'):
                    with self.assertRaises(HTTPError) as error:urlopen(base+path)
                    self.assertEqual(error.exception.code,404)
                    error.exception.close()
                for path in ('/api/publisher/publish','/api/publisher/save','/api/export-entry'):
                    request=Request(base+path,data=b'{}',headers={'Content-Type':'application/json','X-Recopile-Token':token})
                    with self.assertRaises(HTTPError) as error:urlopen(request)
                    self.assertEqual(error.exception.code,404)
                    error.exception.close()
            finally:
                server.shutdown();server.server_close();app.shutdown();app.media.pool.shutdown(wait=True);app.jobs.pool.shutdown(wait=True)

if __name__=='__main__':unittest.main()
