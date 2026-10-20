#!/usr/bin/env python3
"""Check Steam discovery UI with local manifests and an inert client fixture."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from browser_check import CDP
from recopile.service import Launcher
from recopile.server import create_server


def manifest(root, app_id, title):
    folder = root / 'steamapps'
    (folder / 'common' / title).mkdir(parents=True, exist_ok=True)
    file = folder / f'appmanifest_{app_id}.acf'
    file.write_text('"AppState" { "appid" "' + str(app_id) + '" "name" "' + title + '" "StateFlags" "4" "installdir" "' + title + '" }')
    return file


def main():
    cdp = CDP(9227)
    output = ROOT / '.local/review/steam'
    checks = []
    with tempfile.TemporaryDirectory(prefix='recopile-steam-browser-') as temporary:
        root = Path(temporary)
        client = root / 'Steam'
        extra = root / 'Second SteamLibrary'
        fh5 = manifest(client, 1551360, 'Forza Horizon 5')
        manifest(client, 1895880, 'Ratchet & Clank Rift Apart')
        manifest(client, 70, 'Unrelated Steam game')
        manifest(extra, 1293830, 'Forza Horizon 4')
        manifest(extra, 123, 'Another unrelated game')
        client_files = {str(file): file.read_bytes() for file in client.rglob('*') if file.is_file()}
        script = root / 'inert-steam.py'
        launched = root / 'launch-arguments.json'
        script.write_text('import json,sys,time\nfrom pathlib import Path\nPath(' + repr(str(launched)) + ').write_text(json.dumps(sys.argv[1:]))\ntime.sleep(1.2)\n')
        with patch('recopile.steam.client_roots', return_value=[client]), patch('recopile.steam.client_command', return_value=[sys.executable, str(script)]):
            app = Launcher(ROOT, root / 'state', automatic=False, scan_steam=True)
            app.save_preferences({'games_dir': str(root / 'library'), 'language': 'en'})
            app.finish_notice({'accepted': True})
            assert not app.steam.enabled() and app.steam.state()['installed']==0
            app.request_media = lambda data: {'queued': 0}
            server = create_server(app, 0)
            threading.Thread(target=server.serve_forever, daemon=True).start()

            def language(code):
                cdp.evaluate("(()=>{const e=document.querySelector('.compact-language select');e.value=" + json.dumps(code) + ";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
                cdp.wait('document.documentElement.lang===' + json.dumps(code))

            def nav(label):
                cdp.evaluate('[...document.querySelectorAll(".main-nav button")].find(b=>b.querySelector("span")?.textContent===' + json.dumps(label) + ').click()')

            def no_overflow():
                assert not cdp.evaluate("document.documentElement.scrollWidth>innerWidth || [...document.querySelectorAll('dialog[open]')].some(d=>d.scrollWidth>d.clientWidth+1)")

            try:
                cdp.call('Page.navigate', {'url': f'http://127.0.0.1:{server.server_port}/'})
                cdp.wait("document.querySelector('.game-card')")
                nav('My games')
                cdp.wait("document.querySelector('.empty')")
                assert app.store.stats()['installed']==0
                cdp.click('Collections')
                cdp.wait("document.querySelector('.steam-enable')")
                assert cdp.evaluate("document.querySelector('.steam-library-heading p').textContent")=='Discovery is off.'
                assert not cdp.evaluate("Boolean(document.querySelector('.steam-rescan'))")
                cdp.click('Enable discovery')
                cdp.wait("document.querySelector('.steam-rescan') && document.querySelector('.steam-library-heading p').textContent==='2 collection games found locally'")
                assert app.steam.enabled()
                assert app.store.game('steam-70') is None
                cdp.click('Scan Steam')
                cdp.wait("!document.querySelector('.steam-rescan').disabled")
                assert app.store.stats()['installed']==2
                assert not launched.exists()
                nav('My games')
                cdp.wait("document.querySelectorAll('.game-card').length===2")
                assert cdp.evaluate("[...document.querySelectorAll('.game-title')].map(e=>e.textContent).sort()") == ['Forza Horizon 5','Ratchet & Clank: Rift Apart']
                assert cdp.evaluate("[...document.querySelectorAll('.game-card .cover-badge')].every(e=>e.textContent==='Steam')")
                cdp.click('Collections')
                cdp.wait("document.querySelector('.steam-library-panel.compact')")
                checks.append('Discovery is off by default; enabling from Collections imports only FH5 and Rift Apart and leaves unrelated Steam titles out')

                cdp.click('Steam library settings')
                cdp.wait("document.querySelector('#steam-library-path')")
                cdp.input('#steam-library-path', str(extra / 'steamapps'))
                cdp.click('Add Steam library')
                cdp.wait("document.querySelectorAll('.steam-library-row').length===2 && !document.querySelector('.steam-rescan').disabled")
                assert app.steam.state()['installed'] == 3
                assert app.preferences()['steam_libraries'] == [str(extra)]
                for code, title in [('en', 'Steam · collection games'), ('pl', 'Steam · gry z kolekcji'), ('hu', 'Steam · gyűjteményjátékok')]:
                    language(code)
                    cdp.wait('document.querySelector(".steam-library-heading h2").textContent===' + json.dumps(title))
                    cdp.capture(output / ('steam-settings-' + code + '.png'))
                    no_overflow()
                cdp.capture(output / 'steam-settings-compact.png', 447, 800)
                no_overflow()
                language('en')
                cdp.evaluate("document.querySelector('.steam-library-row button[aria-label=\"Remove extra Steam library\"]').click()")
                cdp.wait("document.querySelectorAll('.steam-library-row').length===1 && !document.querySelector('.steam-rescan').disabled")
                assert app.steam.state()['installed'] == 2
                assert (extra / 'steamapps/appmanifest_1293830.acf').is_file()
                assert app.store.game('steam-123') is None
                checks.append('An extra folder also imports only collection App IDs; settings and disable switch work in EN/PL/HU at 447 px')

                cdp.click('Collections')
                cdp.wait("document.querySelector('.collection-tile')")
                cdp.evaluate("[...document.querySelectorAll('.collection-tile')].find(e=>e.textContent.includes('Forza Collection')).click()")
                cdp.wait("document.querySelector('[data-title=\"Forza Horizon 5\"] .collection-play')")
                selector = '[data-title="Forza Horizon 5"]'
                card = cdp.evaluate('document.querySelector(' + json.dumps(selector) + ').textContent')
                assert 'Found in Steam' in card and 'Launch in Steam' in card
                assert 'Steam playtime and achievements · integration planned' in card
                assert not cdp.evaluate('document.querySelector(' + json.dumps(selector) + ').textContent.includes("Buy on Steam")')
                cdp.capture(output / 'steam-forza-collection.png')
                no_overflow()
                cdp.evaluate('document.querySelector(' + json.dumps(selector + ' .collection-play') + ').click()')
                deadline = time.monotonic() + 5
                while not launched.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                assert json.loads(launched.read_text()) == ['-applaunch', '1551360']
                time.sleep(1.4)
                assert app.active_processes() == [] and app.profiles.summary()['launches'] == 0
                cdp.evaluate('[...document.querySelectorAll(' + json.dumps(selector + ' button') + ')].find(b=>b.textContent==="Open details").click()')
                cdp.wait("document.querySelector('dialog[open] .install-info code')")
                assert cdp.evaluate("document.querySelector('dialog[open]').textContent.includes('Steam playtime and achievements are not synchronized yet.')")
                assert cdp.evaluate("document.querySelector('dialog[open] .install-info code').textContent") == str(client / 'steamapps/common/Forza Horizon 5')
                cdp.capture(output / 'steam-detail-compact.png', 447, 800)
                no_overflow()
                cdp.evaluate("document.querySelector('dialog[open] button[aria-label=Close]').click()")
                checks.append('Known App ID links FH5 to PC collection, opens Steam details and forwards numeric launch request to inert client without false playtime')

                cdp.click('All collections')
                cdp.wait("document.querySelector('.collection-tile')")
                cdp.evaluate("[...document.querySelectorAll('.collection-tile')].find(e=>e.textContent.includes('Ratchet & Clank Collection')).click()")
                cdp.wait("document.querySelector('[data-title=\"Ratchet & Clank: Rift Apart\"] .collection-play')")
                assert cdp.evaluate("document.querySelector('[data-title=\"Ratchet & Clank: Rift Apart\"]').textContent.includes('Found in Steam')")
                checks.append('Rift Apart also matches by App ID even when manifest title differs')
                assert client_files == {str(file): file.read_bytes() for file in client.rglob('*') if file.is_file()}

                fh5.unlink()
                cdp.click('All collections')
                cdp.wait("document.querySelector('.steam-rescan')")
                cdp.click('Scan Steam')
                cdp.wait("document.querySelector('.steam-library-heading p').textContent==='1 collection games found locally'")
                assert app.store.stats()['installed'] == 1
                nav('My games')
                cdp.wait("document.querySelectorAll('.game-card').length===2")
                cdp.click('Installed')
                cdp.wait("document.querySelectorAll('.game-card').length===1")
                assert cdp.evaluate("document.querySelector('.game-title').textContent") == 'Ratchet & Clank: Rift Apart'
                checks.append('Rescan notices a removed manifest and removes stale installed/ready status')
                cdp.click('Collections')
                cdp.wait("document.querySelector('.steam-library-panel')")
                cdp.click('Steam library settings')
                cdp.wait("document.querySelector('.steam-library-panel [role=switch][aria-checked=true]')")
                cdp.evaluate("document.querySelector('.steam-library-panel [role=switch]').click()")
                cdp.wait("document.querySelector('.steam-library-panel [role=switch][aria-checked=false]')")
                assert not cdp.evaluate("Boolean(document.querySelector('.steam-rescan') || document.querySelector('#steam-library-path'))")
                assert app.store.stats()['installed']==0 and not app.steam.enabled()
                cdp.call('Page.reload')
                cdp.wait("document.querySelector('.game-card')")
                cdp.click('Collections')
                cdp.wait("document.querySelector('.steam-enable')")
                assert cdp.evaluate("document.querySelector('.steam-library-heading p').textContent")=='Discovery is off.'
                checks.append('Disabling is remembered, removes automatic links and hides scanning controls; game files and local history remain untouched')
                assert not cdp.errors, cdp.errors
                report = {'checks': checks, 'console_errors': cdp.errors,
                          'actual_steam_client_executed': False, 'actual_games_executed': False,
                          'gameplay_validated': False}
                output.mkdir(parents=True, exist_ok=True)
                (output / 'steam-browser-check.json').write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps(report, indent=2))
            finally:
                cdp.call('Page.navigate', {'url': 'http://127.0.0.1:4785/'})
                server.shutdown()
                server.server_close()
                app.shutdown()
                app.media.pool.shutdown(wait=True)
                app.jobs.pool.shutdown(wait=True)


if __name__ == '__main__':
    main()
