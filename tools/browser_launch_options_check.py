#!/usr/bin/env python3
"""Check the Play/official-launcher dialog against a real local HTTP service.

GPL-3.0-only. Copyright (C) 2026 MASELKO-95. Added 2026-10-21.
Uses inert executables and synthetic input markers, never game data.
Requires Chromium, Xvfb and the built frontend on Linux.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from browser_check import CDP
from recopile.server import create_server
from tests.test_launch_options import LaunchOptionsTests


def main():
    output = ROOT / '.local/review/launch-options'
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    fixture = LaunchOptionsTests()
    fixture.setUp()
    app = fixture.app
    app.save_preferences({'language': 'pl'})
    app.finish_notice({'accepted': True})
    app.request_media = lambda data: {'queued': 0}
    server = create_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    cdp = None
    with tempfile.TemporaryDirectory(prefix='recopile-launch-choice-browser-') as profile, (output / 'browser.log').open('w') as log:
        browser = subprocess.Popen(['xvfb-run', '-a', shutil.which('chromium'), '--headless=new',
            '--no-sandbox', '--disable-gpu', '--disable-background-networking', '--no-first-run',
            '--remote-debugging-port=9231', '--user-data-dir=' + profile, 'about:blank'],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    cdp = CDP(9231)
                    break
                except OSError:
                    assert browser.poll() is None, 'Chromium exited'
                    time.sleep(.1)
            assert cdp is not None, 'DevTools did not start'
            cdp.call('Emulation.setDeviceMetricsOverride', {'width':1440, 'height':1000, 'deviceScaleFactor':1, 'mobile':False})
            cdp.call('Page.navigate', {'url':f'http://127.0.0.1:{server.server_port}/'})
            cdp.wait("document.querySelector('.game-card')")
            cdp.input('input[aria-label="Szukaj gry w katalogu"]', 'Forza Horizon')
            cdp.wait("[...document.querySelectorAll('.game-title')].some(e=>e.textContent==='Forza Horizon')")
            cdp.click('Forza Horizon')
            cdp.wait("document.querySelector('dialog[open] .detail-body')")

            def close_top():
                cdp.evaluate("[...document.querySelectorAll('dialog[open]')].at(-1).querySelector('.modal-head button').click()")

            def click_dialog(label):
                assert cdp.evaluate("(()=>{const d=[...document.querySelectorAll('dialog[open]')].at(-1);const b=[...d.querySelectorAll('button')].find(b=>b.textContent.trim()==="+json.dumps(label)+");if(!b||b.disabled)return false;b.click();return true;})()"), label

            def ask():
                click_dialog('Graj')
                cdp.wait("[...document.querySelectorAll('dialog[open] h2')].some(e=>e.textContent==='Jak uruchomić grę?')")

            def observed():
                deadline = time.monotonic() + 5
                while not fixture.output.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                fixture.wait()
                value = json.loads(fixture.output.read_text())
                fixture.output.unlink()
                return value

            ask()
            assert not fixture.output.exists() and not app.active_processes()
            close_top()
            cdp.wait("document.querySelectorAll('dialog[open]').length===1")
            assert not fixture.output.exists()
            checks.append('First Play asks; closing the question launches nothing')

            ask()
            cdp.capture(output / 'choice-pl.png')
            cdp.evaluate("[...document.querySelectorAll('dialog[open]')].at(-1).querySelector('input[type=checkbox]').click()")
            click_dialog('Graj od razu')
            cdp.wait("document.querySelectorAll('dialog[open]').length===1")
            assert observed()['args'] == []
            assert app.detail(fixture.ident)['launch_options']['preferred'] == 'game'
            click_dialog('Graj')
            observed()
            assert cdp.evaluate("document.querySelectorAll('dialog[open]').length") == 1
            checks.append('Remembered direct Play skips the question and starts the game fixture')

            click_dialog('Opcje uruchamiania')
            cdp.wait("document.querySelectorAll('dialog[open]').length===2")
            assert cdp.evaluate("[...document.querySelectorAll('dialog[open]')].at(-1).querySelector('input').checked")
            cdp.evaluate("[...document.querySelectorAll('dialog[open]')].at(-1).querySelector('input').click()")
            launches = app.profiles.summary()['launches']
            click_dialog('Oryginalny launcher Pinyon Shift')
            cdp.wait("document.querySelectorAll('dialog[open]').length===1")
            result = observed()
            assert result['args'] == []
            assert result['environment']['PINYON_SHIFT_SOURCE_ROOT'] == str(fixture.source)
            assert result['environment']['PINYON_SHIFT_STATE_ROOT'] == fixture.install['pinyon_state_root']
            assert app.profiles.summary()['launches'] == launches
            assert app.detail(fixture.ident)['launch_options']['preferred'] == 'ask'
            ask()
            close_top()
            cdp.wait("document.querySelectorAll('dialog[open]').length===1")
            click_dialog('Ustawienia gry')
            observed()
            assert app.profiles.summary()['launches'] == launches
            checks.append('Launch options forgets the preference; official launcher and Game settings share state without false playtime')

            for code, options, title in [('en','Launch options','How would you like to launch?'),
                                          ('hu','Indítási beállítások','Hogyan szeretnéd indítani a játékot?'),
                                          ('pl','Opcje uruchamiania','Jak uruchomić grę?')]:
                close_top()
                cdp.wait("!document.querySelector('dialog[open]')")
                cdp.evaluate("(()=>{const s=document.querySelector('.compact-language select');s.value="+json.dumps(code)+";s.dispatchEvent(new Event('change',{bubbles:true}));})()")
                cdp.wait('document.documentElement.lang===' + json.dumps(code))
                cdp.click('Forza Horizon')
                cdp.wait("document.querySelector('dialog[open] .detail-body')")
                click_dialog(options)
                cdp.wait("[...document.querySelectorAll('dialog[open] h2')].some(e=>e.textContent==="+json.dumps(title)+")")
                cdp.capture(output / ('choice-' + code + '-compact.png'), 320, 800)
                assert not cdp.evaluate("document.documentElement.scrollWidth>innerWidth || [...document.querySelectorAll('dialog[open]')].some(d=>d.scrollWidth>d.clientWidth+1)")
                close_top()
                cdp.wait("document.querySelectorAll('dialog[open]').length===1")
            checks.append('Polish, English and Hungarian dialog fit a 320px viewport')
            assert not cdp.errors, cdp.errors
            report = {'checks':checks, 'console_errors':cdp.errors, 'game_data_used':False}
            (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps(report, ensure_ascii=False))
        except Exception:
            if cdp:
                cdp.capture(output / 'failure.png')
                print(json.dumps({'ui':cdp.evaluate("({dialogs:[...document.querySelectorAll('dialog[open]')].map(d=>d.innerText),toasts:[...document.querySelectorAll('.toast')].map(e=>e.innerText),buttons:[...document.querySelectorAll('dialog[open] button')].map(b=>({text:b.textContent,disabled:b.disabled}))})"), 'console_errors':cdp.errors}, ensure_ascii=False), flush=True)
            raise
        finally:
            if cdp:
                try: cdp.call('Browser.close')
                except (OSError, RuntimeError): pass
                cdp.socket.close()
            if browser.poll() is None:
                os.killpg(browser.pid, signal.SIGTERM)
            browser.wait(timeout=10)
            server.shutdown()
            server.server_close()
            fixture.tearDown()


if __name__ == '__main__':
    main()
