#!/usr/bin/env python3
"""Start a built Linux application with isolated data and updates disabled.

This checks packaged UI/backend startup, not game compatibility or an OS install.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from browser_check import CDP

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from recopile import __version__

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program',type=Path)
    args=parser.parse_args()
    program=args.program.resolve()
    out=ROOT/'.local/review/installers';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='recopile-desktop-smoke-') as temporary:
        root=Path(temporary)
        env={**os.environ,'RECOPILE_NO_UPDATES':'1','RECOPILE_DESKTOP_STATE':str(root/'state'),
             'RECOPILE_LIBRARY_ROOT':str(root/'library'),'XDG_CONFIG_HOME':str(root/'config'),
             'XDG_CACHE_HOME':str(root/'cache'),'XDG_DATA_HOME':str(root/'data'),
             'APPIMAGE_EXTRACT_AND_RUN':'1'}
        log_path=out/(program.name+'.log')
        with log_path.open('w') as log:
            proc=subprocess.Popen(['xvfb-run','-a',str(program),'--no-sandbox','--disable-gpu','--remote-debugging-port=9228'],
                                  env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            cdp=None
            deadline=time.monotonic()+55
            while time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError(log_path.read_text()[-6000:])
                try: cdp=CDP(9228);break
                except (OSError,StopIteration,KeyError):time.sleep(.15)
            if not cdp:raise RuntimeError('Desktop did not expose test page: '+log_path.read_text()[-6000:])
            cdp.wait("document.querySelector('.app-attribution')",timeout=25)
            boot=cdp.evaluate("fetch('/api/bootstrap').then(r=>r.json())")
            assert boot['version']==__version__,boot['version']
            assert not boot['settings']['steam_enabled']
            assert boot['stats']['total']>18000
            assert boot['app_notice']['required']
            assert 'publisher_mode' not in boot['settings']
            assert not cdp.evaluate("[...document.querySelectorAll('aside button,nav button')].some(b=>/publisher|wydawca/i.test(b.textContent))")
            origin=cdp.evaluate('location.origin')
            try:
                urlopen(origin+'/api/publisher').close()
                raise AssertionError('Unexpected player publishing API')
            except HTTPError as exc:assert exc.code==404,exc.code
            cdp.evaluate("document.querySelector('dialog input[type=checkbox]').click();document.querySelector('dialog .modal-actions .primary').click()")
            cdp.wait("!document.querySelector('dialog[open]')")
            cdp.click('Measurements')
            cdp.wait("document.querySelector('.performance-page')")
            cdp.capture(out/(program.name+'.png'))
            state=cdp.evaluate("fetch('/api/performance').then(r=>r.json())")
            assert state['sessions']==[]
            assert not cdp.errors,cdp.errors
            report={'program':program.name,'version':boot['version'],'catalog_titles':boot['stats']['total'],
                    'steam_enabled':False,'packaged_backend':True,'first_run_consent':True,
                    'measurements_page':True,'console_errors':cdp.errors,
                    'publisher_absent':True,
                    'updates_disabled_for_smoke':True,'os_install_performed':False,'game_programs_executed':False}
            (out/(program.name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
        finally:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait()

if __name__=='__main__':main()
