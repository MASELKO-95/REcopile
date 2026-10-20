import React, {useState} from 'react';
import {ArrowClockwise, FolderOpen, GameController, X} from '@phosphor-icons/react';
import {ago, Badge, Spinner} from './ui.jsx';

export function SteamLibraryPanel({boot, action, compact=false, onSettings}) {
  const [busy,setBusy]=useState(false),[path,setPath]=useState('');
  const steam=boot.steam || {installed:0,libraries:[]};
  const enabled=steam.enabled===true;
  async function run(url,body={},message='Biblioteka Steam została odświeżona.') {
    setBusy(true);
    try { const result=await action(url,body,message); setPath(''); return result; }
    catch {} finally { setBusy(false); }
  }
  async function browse() {
    try { const result=await action('/api/pick',{mode:'folder'}); if(result.path)setPath(result.path); } catch {}
  }
  const configure=value=>run('/api/steam/settings',{enabled:value},value?'Wykrywanie gier z kolekcji włączone.':'Wykrywanie gier z kolekcji wyłączone.');
  return <section className={'panel steam-library-panel '+(compact?'compact':'')} aria-label="Steam · gry z kolekcji">
    <div className="steam-library-heading"><GameController size={25}/><div><h2>Steam · gry z kolekcji</h2><p>{!enabled?'Wykrywanie jest wyłączone.':steam.checked_at?`${steam.installed} gier z kolekcji wykrytych lokalnie`:'Nie wykonano jeszcze skanowania bibliotek Steam.'}</p></div>
      {enabled?<button type="button" className="outline steam-rescan" disabled={busy} onClick={()=>run('/api/steam/scan')}>{busy?<Spinner/>:<ArrowClockwise size={17}/>}Skanuj Steam</button>:compact?<button type="button" className="outline steam-enable" disabled={busy} onClick={()=>configure(true)}>{busy?<Spinner/>:<GameController size={17}/>}Włącz wykrywanie</button>:null}
    </div>
    <p className="form-help">Opcja jest dobrowolna i domyślnie wyłączona. Po włączeniu sprawdzamy przy starcie tylko gry z kolekcji RE:COPILE.</p>
    {compact ? <button type="button" className="text-link" onClick={onSettings}>Ustawienia bibliotek Steam</button> : <>
      <div className="setting-toggle"><div><strong>Połącz gry z kolekcji ze Steamem</strong><p>Wykrywaj zainstalowane wersje PC z naszych kolekcji, bez logowania do konta Steam.</p></div><button type="button" className={'switch '+(enabled?'on':'')} role="switch" aria-label="Połącz gry z kolekcji ze Steamem" aria-checked={enabled} disabled={busy} onClick={()=>configure(!enabled)}><span/></button></div>
      {enabled && <>
      <p className="form-help">Sprawdzamy wyłącznie gry z kolekcji. Gry pozostają w folderach Steama; skanowanie nie pobiera okładek.</p>
      {steam.checked_at && !steam.client_available && <p className="steam-warning">Nie znaleziono klienta Steam. Wykryte gry można uruchomić po jego zainstalowaniu i ponownym skanowaniu.</p>}
      <div className="steam-library-list">{steam.libraries.map(library=><div className="steam-library-row" key={library.path}>
        <FolderOpen size={19}/><div><code translate="no">{library.path}</code><small>{library.available?`${library.games || 0} gier`:'Dysk lub folder niedostępny'}</small>{library.warning && <small>{library.warning}</small>}</div>
        {(boot.settings.steam_libraries || []).includes(library.path) && <button type="button" className="icon-button" disabled={busy} aria-label="Usuń dodatkową bibliotekę Steam" onClick={()=>run('/api/steam/library',{path:library.path,remove:true})}><X size={17}/></button>}
      </div>)}</div>
      {!steam.libraries.length && <p className="form-help">Nie znaleziono biblioteki? Wskaż folder Steam lub SteamLibrary na swoim dysku.</p>}
      <label htmlFor="steam-library-path">Dodatkowa biblioteka Steam</label>
      <div className="inline-field steam-path-field"><input id="steam-library-path" value={path} placeholder="Folder Steam lub SteamLibrary" onChange={e=>setPath(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();if(path.trim()&&!busy)run('/api/steam/library',{path});}}}/><button type="button" className="outline" disabled={busy} onClick={browse}><FolderOpen size={17}/>Wybierz</button></div>
      <button type="button" className="outline steam-add-library" disabled={busy || !path.trim()} onClick={()=>run('/api/steam/library',{path})}>Dodaj bibliotekę Steam</button>
      <p className="form-help">Ostatnie skanowanie: {ago(steam.checked_at)}</p>
      {steam.warnings?.length>0 && <p className="steam-warning">Niektórych plików Steam nie udało się odczytać. Dostępne instalacje zostały dodane.</p>}
      <Badge kind="muted">Czas i osiągnięcia Steam · integracja planowana</Badge>
      </>}
    </>}
  </section>;
}
