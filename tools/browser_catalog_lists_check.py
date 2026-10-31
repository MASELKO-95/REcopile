#!/usr/bin/env python3
"""Check project lists and downloads translations with isolated player state.

Copyright (C) 2026 MASELKO-95. GPL-3.0-only. Added 2026-10-30.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from browser_check import CDP
from recopile.server import create_server
from recopile.service import Launcher

def main():
    with tempfile.TemporaryDirectory(prefix='recopile-lists-browser-') as temporary:
        root=Path(temporary)
        app=Launcher(ROOT,root/'state',automatic=False,scan_steam=False)
        app.save_preferences({'games_dir':str(root/'library'),'check_updates':False,'launcher_repo':''})
        app.finish_notice({'accepted':True})
        app.store.put('jobs','translation-fixture',{'id':'translation-fixture','kind':'check','title':'Sprawdzanie aktualizacji',
            'target':'all-sources','status':'running','progress':35,'message':'Sprawdzanie: Example Port','created_at':time.time(),'total':0})
        server=create_server(app,0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}/'
        log=(ROOT/'.local/review/catalog-list-browser.log').open('w')
        browser=subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-gpu','--no-first-run',
            '--remote-debugging-port=9235','--user-data-dir='+str(root/'browser'),url],stdout=log,stderr=log)
        checks=[]
        try:
            deadline=time.monotonic()+25
            while True:
                try:cdp=CDP(9235);break
                except (OSError,StopIteration,KeyError):
                    if time.monotonic()>deadline:raise
                    time.sleep(.1)
            cdp.wait("document.querySelector('.app-shell')")
            def language(code):
                cdp.evaluate("(()=>{const e=document.querySelector('.compact-language select');e.value="+json.dumps(code)+";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
                cdp.wait('document.documentElement.lang==='+json.dumps(code))
            language('en');cdp.evaluate("[...document.querySelectorAll('.main-nav button')].find(b=>b.textContent.startsWith('Downloads')).click()")
            cdp.wait("document.querySelector('.page-heading p')?.textContent==='Installations and updates, all in one place.'")
            assert cdp.evaluate("document.querySelector('.job-title strong').textContent")=='Checking for updates'
            assert cdp.evaluate("document.querySelector('.job-body>p').textContent")=='Checking: Example Port'
            checks.append('English downloads heading, task title and dynamic task message')
            cdp.click('Emulators');cdp.wait("document.querySelector('.engine-list')")
            assert cdp.evaluate("[...document.querySelectorAll('.engine-card h2')].map(e=>e.textContent).includes('Xenia / custom adapter')")
            checks.append('English Xbox 360 engine name')
            for code,label in [('pl','Źródła'),('en','Sources'),('hu','Források')]:
                language(code);cdp.click(label)
                cdp.wait("document.querySelectorAll('.catalog-list-entries article').length===10")
                counts=cdp.evaluate("fetch('/api/catalog-lists').then(r=>r.json()).then(d=>d.lists.map(l=>({total:l.total,missing:l.missing})))")
                assert len(counts)==2 and all(l['total']>50 and not l['missing'] for l in counts),counts
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':320,'height':800,'deviceScaleFactor':1,'mobile':False})
                assert not cdp.evaluate('document.documentElement.scrollWidth>innerWidth'),code
                checks.append(code+': list statuses, pagination and 320px layout')
            language('en')
            cdp.input('.catalog-lists input[type=search]','Geometry Wars')
            cdp.wait("document.querySelectorAll('.catalog-list-entries article').length===1")
            cdp.evaluate("document.querySelector('.catalog-list-entries .text-link').click()")
            cdp.wait("document.querySelector('dialog[open]')")
            assert cdp.evaluate("document.querySelector('dialog h2').textContent")=='Geometry Wars: Retro Evolved 2'
            assert cdp.evaluate("[...document.querySelectorAll('dialog button')].some(b=>b.textContent.includes('Install port'))")
            assert not list((root/'state/covers').glob('*'))
            assert not cdp.errors,cdp.errors
            checks.append('List search opens the actual game and its Install port action without fetching artwork')
            cdp.evaluate("document.querySelector('dialog .modal-head .icon-button').click()")
            cdp.wait("!document.querySelector('dialog[open]')")
            cdp.input('.catalog-lists input[type=search]',"WWE '12")
            cdp.wait("document.querySelectorAll('.catalog-list-entries article').length===1")
            cdp.evaluate("document.querySelector('.catalog-list-entries .text-link').click()")
            cdp.wait("document.querySelector('dialog[open]')")
            assert cdp.evaluate("[...document.querySelectorAll('dialog button')].some(b=>b.textContent.includes('Download Windows port'))")
            checks.append('Windows-only packages offer a clearly labeled managed download on Linux')
            report={'checks':checks,'console_errors':cdp.errors,'gameplay_tested':False}
            (ROOT/'.local/review/catalog-list-browser.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
        finally:
            browser.terminate()
            try:browser.wait(timeout=8)
            except subprocess.TimeoutExpired:browser.kill();browser.wait()
            log.close();server.shutdown();server.server_close();app.shutdown()
            app.jobs.pool.shutdown(wait=True);app.media.pool.shutdown(wait=True)

if __name__=='__main__':main()
