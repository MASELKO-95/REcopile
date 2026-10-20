#!/usr/bin/env python3
"""Check local license consent with inert fixtures; never launch game programs."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from browser_check import CDP
from recopile.service import Launcher
from recopile.server import create_server


def main():
    cdp=CDP(9227)
    output=ROOT/'.local/review/guides-collections-final'
    checks=[]
    with tempfile.TemporaryDirectory(prefix='recopile-license-browser-') as temporary:
        root=Path(temporary)
        app=Launcher(ROOT,root/'state',automatic=False)
        app.save_preferences({'games_dir':str(root/'library'),'language':'en'})
        app.request_media=lambda data: {'queued':0}
        program=root/'fixture.exe';program.write_bytes(b'Inert UI fixture; never executed')
        game=app.add_local_game({'title':'Ratchet & Clank: Rift Apart','platform':'other',
            'path':str(program),'trusted':True,'runner':'native'})
        manifest={'schema_version':1,'id':'consent-fixture','name':'License consent fixture','author':'Test',
            'version':'1','game_id':game['id'],'supported_versions':['local'],'systems':['linux','windows'],
            'license':'LicenseRef-Fixture','files':[{'source':'payload/data.txt','target':'data.txt',
                'sha256':hashlib.sha256(b'fixture data').hexdigest()}]}
        def package(filename,text):
            path=root/filename
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('manifest.json',json.dumps(manifest))
                archive.writestr('README.md','Inert fixture instructions')
                archive.writestr('LICENSE',text)
                archive.writestr('payload/data.txt',b'fixture data')
            return path
        valid=package('valid.zip','Fixture license terms')
        changed=package('changed.zip','Changed fixture license terms')
        empty=package('empty.zip','  ')
        server=create_server(app,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            cdp.call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/'})
            cdp.wait("document.querySelector('.app-attribution')")
            assert cdp.evaluate("document.querySelector('dialog .modal-actions .primary').disabled")
            cdp.evaluate("document.querySelectorAll('dialog .tabs button')[1].click()")
            cdp.wait("document.querySelector('dialog .document-text')?.textContent.includes('GNU GENERAL PUBLIC LICENSE')")
            cdp.evaluate("document.querySelector('dialog input[type=checkbox]').click()")
            cdp.evaluate("document.querySelector('dialog .modal-actions .primary').click()")
            cdp.wait("!document.querySelector('dialog[open]')")
            assert app.preferences()['app_license_accepted'] is True
            checks.append('Application requires explicit GPLv3 consent and stores acceptance locally')
            cdp.click('Collections')
            cdp.wait("document.querySelector('.collection-tile')")
            cdp.evaluate("[...document.querySelectorAll('.collection-tile')].find(b=>b.textContent.includes('Ratchet & Clank Collection')).click()")
            cdp.wait('''document.querySelector('[data-title="Ratchet & Clank: Rift Apart"] .collection-play')?.textContent.includes('Play')''')
            cdp.evaluate('''document.querySelector('[data-title="Ratchet & Clank: Rift Apart"] .collection-pc-actions button.outline').click()''')
            cdp.wait("document.querySelector('dialog .detail-note')?.textContent.includes('Local PC installation')")
            cdp.evaluate("document.querySelector('dialog .modal-head .icon-button').click()")
            checks.append('An existing PC installation exposes Play and opens PC details without an emulator instruction')
            cdp.click('Workshop')
            cdp.wait("document.querySelector('.mod-import')")
            def inspect(path):
                cdp.input('.mod-import input',str(path))
                cdp.evaluate("document.querySelector('.mod-import button.primary').click()")
                cdp.wait("document.querySelector('.project-license-consent input')")
            inspect(valid)
            assert cdp.evaluate("document.querySelector('.project-license-consent input').disabled")
            cdp.evaluate("document.querySelector('dialog input[type=checkbox]').click()")
            assert cdp.evaluate("document.querySelector('dialog .modal-actions .primary').disabled")
            cdp.evaluate("document.querySelectorAll('dialog .tabs button')[1].click()")
            cdp.evaluate("document.querySelector('.project-license-consent input').click()")
            assert not cdp.evaluate("document.querySelector('dialog .modal-actions .primary').disabled")
            cdp.capture(output/'mod-license-consent.png')
            cdp.evaluate("document.querySelector('dialog .modal-actions .primary').click()")
            cdp.wait("!document.querySelector('dialog[open]')")
            installed=app.store.list('mods')
            assert len(installed)==1 and installed[0]['license_accepted'] and not installed[0]['active']
            checks.append('Mod README acknowledgment alone is insufficient; separate license consent authorizes an inert prepared package')
            inspect(changed)
            assert cdp.evaluate("!document.querySelector('.project-license-consent input').checked && document.querySelector('.project-license-consent input').disabled")
            cdp.evaluate("document.querySelector('dialog .modal-head .icon-button').click()")
            inspect(empty)
            cdp.evaluate("document.querySelectorAll('dialog .tabs button')[1].click()")
            assert cdp.evaluate("document.querySelector('.project-license-consent input').disabled && document.querySelector('dialog .modal-actions .primary').disabled")
            cdp.wait("document.querySelector('dialog').textContent.includes('Installation blocked')")
            checks.append('Changed mod licenses reset consent; blank licenses block installation')
            assert not cdp.errors,cdp.errors
            report={'checks':checks,'console_errors':cdp.errors,'game_programs_executed':False}
            output.mkdir(parents=True,exist_ok=True)
            (output/'license-browser-check.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
        finally:
            cdp.call('Page.navigate',{'url':'http://127.0.0.1:4785/'})
            server.shutdown();server.server_close()
            app.shutdown();app.media.pool.shutdown(wait=True);app.jobs.pool.shutdown(wait=True)


if __name__=='__main__':main()
