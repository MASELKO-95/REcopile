#!/usr/bin/env python3
"""Exercise collection launch and profile recording with inert local programs."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from browser_check import CDP
from recopile.service import Launcher
from recopile.server import create_server
from recopile.storage import game_id


def main():
    cdp=CDP(9227)
    output=ROOT/'.local/review/collection-play'
    checks=[]
    with tempfile.TemporaryDirectory(prefix='recopile-series-play-') as temporary:
        root=Path(temporary)
        app=Launcher(ROOT,root/'state',automatic=False)
        app.save_preferences({'games_dir':str(root/'library'),'language':'en'})
        app.finish_notice({'accepted':True})
        app.request_media=lambda data:{'queued':0}
        program=root/'inert-program'
        program.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(1.2)\n')
        program.chmod(0o755)
        ids=[game_id('xbox360','Forza Horizon'),game_id('xbox360','Forza Horizon 2')]
        for ident in ids:app.register_executable(ident,{'path':str(program),'trusted':True})
        pc=app.add_local_game({'title':'Forza Horizon 3','platform':'other','path':str(program),'trusted':True})
        ids.append(pc['id'])
        other=app.profiles.create('Second player')
        server=create_server(app,0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        def language(code):
            cdp.evaluate("(()=>{const e=document.querySelector('.compact-language select');e.value="+json.dumps(code)+";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
            cdp.wait('document.documentElement.lang==='+json.dumps(code))
        def no_overflow():
            assert not cdp.evaluate("document.documentElement.scrollWidth>innerWidth || [...document.querySelectorAll('dialog[open]')].some(d=>d.scrollWidth>d.clientWidth+1)")
        try:
            cdp.call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/'})
            cdp.wait("document.querySelector('.game-card')")
            cdp.click('Collections')
            cdp.wait("document.querySelector('.collection-tile')")
            cdp.evaluate("[...document.querySelectorAll('.collection-tile')].find(b=>b.textContent.includes('Forza Collection')).click()")
            cdp.wait("document.querySelectorAll('.collection-series-game').length===6")
            titles=cdp.evaluate("[...document.querySelectorAll('.collection-series-game h3')].map(e=>e.textContent)")
            assert titles==['Forza Horizon',*[f'Forza Horizon {n}' for n in range(2,7)]],titles
            assert cdp.evaluate('''document.querySelector('[data-title="Forza Horizon 3"] a[href*="xbox.com"]')!==null''')
            assert not cdp.evaluate('''[...document.querySelectorAll('[data-title="Forza Horizon 3"] a')].some(a=>a.href.includes('steampowered.com'))''')
            cdp.capture(output/'forza-series-order.png')
            checks.append('Horizon 1–6 appear in order with recompilations and PC editions together; FH3 links Microsoft Store/Xbox')
            for index,title in enumerate(titles[:3],1):
                selector='[data-title='+json.dumps(title)+']'
                cdp.evaluate('document.querySelector('+json.dumps(selector+' .collection-play')+').click()')
                cdp.wait('document.querySelector('+json.dumps(selector+' .collection-pc-actions button.primary')+').disabled')
                cdp.wait('document.querySelector('+json.dumps(selector+' .collection-game-stats')+').textContent.includes("1 launches")')
                assert app.profiles.summary()['launches']==index
            checks.append('Collection Play launches inert programs for FH1/FH2/FH3 and refreshes per-game launch counts after exit')
            cdp.click('View player card')
            cdp.wait("document.querySelectorAll('.profile-game').length===3")
            for ident in ids:
                assert cdp.evaluate('document.querySelector('+json.dumps('[data-game-id="'+ident+'"] .profile-game-metrics')+').textContent.includes("Game achievements · integration planned")')
            assert cdp.evaluate("[...document.querySelectorAll('.game-achievements-pending strong')].every(e=>e.textContent==='—')")
            for code,label in [('en','Your stats for each game'),('hu','Statisztikáid játékonként'),('pl','Twoje statystyki w każdej grze')]:
                language(code)
                cdp.wait('document.querySelector(".profile-game-history h2").textContent==='+json.dumps(label))
                cdp.capture(output/('player-card-'+code+'.png'))
                no_overflow()
            cdp.capture(output/'player-card-compact.png',447,800);no_overflow()
            language('en')
            # Launch the same tracked installation from its per-game player card.
            selector='[data-game-id="'+ids[0]+'"]'
            cdp.evaluate('document.querySelector('+json.dumps(selector+' button.primary')+').click()')
            cdp.wait('document.querySelector('+json.dumps(selector+' button.primary')+').disabled')
            cdp.wait('document.querySelector('+json.dumps(selector+' .profile-game-metrics>div:nth-child(2) strong')+').textContent==="2"')
            cdp.evaluate("(()=>{const e=document.querySelector('.profile-page select');e.value="+json.dumps(other['id'])+";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
            cdp.wait("document.querySelectorAll('.profile-game').length===0 && document.querySelector('.profile-game-history .empty')")
            stats=app.profiles.summary('local')
            assert stats['launches']==4 and len(stats['games'])==3
            assert all(entry['seconds']>=1 and entry['game_achievements']['unlocked'] is None for entry in stats['games'])
            assert app.profiles.summary(other['id'])['launches']==0
            checks.append('Player card shows separate hours/launches, launches a connected game, isolates profiles and leaves game-achievement counts unknown')
            cdp.click('Collections')
            cdp.wait("document.querySelector('.collection-tile')")
            cdp.evaluate("[...document.querySelectorAll('.collection-tile')].find(b=>b.textContent.includes('Forza Collection')).click()")
            cdp.wait("document.querySelectorAll('.collection-series-game').length===6")
            cdp.capture(output/'forza-series-compact.png',447,800);no_overflow()
            assert not cdp.errors,cdp.errors
            report={'checks':checks,'console_errors':cdp.errors,'fixture_launches':stats['launches'],
                    'gameplay_validated':False,'actual_games_executed':False}
            output.mkdir(parents=True,exist_ok=True)
            (output/'collection-play-browser-check.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
        finally:
            cdp.call('Page.navigate',{'url':'http://127.0.0.1:4785/'})
            server.shutdown();server.server_close()
            app.shutdown();app.media.pool.shutdown(wait=True);app.jobs.pool.shutdown(wait=True)


if __name__=='__main__':main()
