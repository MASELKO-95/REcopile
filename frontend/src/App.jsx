import React, { useEffect, useRef, useState } from 'react';
import { GameController, Compass, DownloadSimple, Wrench, GearSix, SquaresFour, Lightning, GithubLogo, Plus, MagnifyingGlass, CaretDown, Play, Check, X, FolderOpen, List, ShieldCheck, CheckCircle, WarningCircle, HardDrives, Cpu, UserCircle, Bell, ArrowRight, Books, Monitor, Heart, Database } from '@phosphor-icons/react';
import { platforms, modes, count, bytes, activeJob, Badge, Spinner, Toggle, Empty, Cover, DeviceBadges, TechnologyBadges } from './ui.jsx';
import {PerformancePage} from './performance.jsx';
import { GameDetail, AddGame } from './dialogs.jsx';
import { Downloads, Sources, Engines, Tools, Settings } from './pages.jsx';
import { AppNotice, ProjectReview, ProfilePage, sponsor } from './community.jsx';
import { SourceEditor, ManualSource,PlatformBadges } from './source-tools.jsx';
import { Collections,WorkshopPage } from './library-extras.jsx';
import { configure,currentLanguage } from './i18n/index.js';
import {LanguageSelect} from './i18n/LanguageSelect.jsx';
import {LaunchOptionsDialog} from './launch-options.jsx';

export function App() {
  const [boot, setBoot] = useState(null), [online, setOnline] = useState(true);
  const [nav, setNav] = useState('catalog'), [platform, setPlatform] = useState('all');
  const [tab, setTab] = useState('all'), [sort, setSort] = useState('featured');
  const [query, setQuery] = useState(''), [debounced, setDebounced] = useState('');
  const [result, setResult] = useState({ games: [], total: 0 }), [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0), [offset, setOffset] = useState(0), [layout, setLayout] = useState('grid');
  const [detail, setDetail] = useState(null), [add, setAdd] = useState(false), [toast, setToast] = useState(null);
  const [review, setReview] = useState(null);
  const [editSource,setEditSource]=useState(null),[manualSource,setManualSource]=useState(null),[showLicense,setShowLicense]=useState(false);
  const [pendingPackage,setPendingPackage]=useState(null);
  const [launchChoice,setLaunchChoice]=useState(null);
  const [requestingCovers,setRequestingCovers]=useState(false);
  configure(boot?.settings.language || currentLanguage());
  const shownUpdates = useRef(new Set());
  const notifiedUpdates = useRef(new Set());
  const search = useRef(null), signature = useRef(''), toastTimer = useRef(null);
  function notice(text, error = false) { clearTimeout(toastTimer.current); setToast({ text, error }); toastTimer.current = setTimeout(() => setToast(null), error ? 8000 : 4500); }
  async function json(url, options) { const response = await fetch(url, options), data = await response.json(); if (!response.ok) throw new Error(data.error || 'Nie udało się wykonać działania.'); return data; }
  async function refresh() { const data = await json('/api/bootstrap'); setBoot(data); setOnline(true); return data; }
  async function action(url, body = {}, message) {
    try {
      if (url === '/api/pick' && window.recopile?.pickPath) return await window.recopile.pickPath(body);
      const data = await json(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Recopile-Token': boot.token }, body: JSON.stringify(body) });
      if (data.review_required) setReview(data);
      if (data.launch_choice_required) {
        setLaunchChoice({...data,request:body});
        return data;
      }
      if (url === '/api/project-info') setReview({ documents:data, readonly:true });
      await refresh(); setRevision(v => v + 1); if (message && !data.review_required) notice(message); return data;
    }
    catch (e) { notice(e.message, true); throw e; }
  }
  const invoke = (url, body, message) => action(url, body, message).catch(() => null);
  const go = next => { setNav(next); setOffset(0); setTab('all'); };
  const changeLanguage = value => invoke('/api/settings',{language:value});
  const catalogPage = ['catalog', 'library', 'device', 'discover', 'recompile', 'other'].includes(nav);
  const selectPlatform = value => { setPlatform(value); setOffset(0); if (!catalogPage) go('catalog'); };
  const requestMedia = (ids,covers) => json('/api/media',{method:'POST',headers:{'Content-Type':'application/json','X-Recopile-Token':boot.token},body:JSON.stringify({game_ids:ids,covers})});
  const openGame = async id => { try { setDetail(await json(`/api/games/${id}`)); requestMedia([id],false).catch(()=>{}); } catch (e) { notice(e.message, true); } };
  async function downloadCovers(ids) {
    setRequestingCovers(true);
    try { const data=await requestMedia(ids,true); notice(data.queued ? 'Pobieranie okładek rozpoczęte. Grafiki pojawią się automatycznie.' : 'Okładki są już pobrane lub zostały niedawno sprawdzone.'); }
    catch(e) { notice(e.message,true); }
    finally { setRequestingCovers(false); }
  }
  useEffect(() => { refresh().catch(e => { setOnline(false); notice(e.message, true); }); return () => clearTimeout(toastTimer.current); }, []);
  useEffect(() => { const t = setTimeout(() => { setDebounced(query); setOffset(0); }, 220); return () => clearTimeout(t); }, [query]);
  useEffect(() => { const h = e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); search.current?.focus(); } }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, []);
  useEffect(() => { const h=() => setShowLicense(true); window.addEventListener('recopile:license',h); return () => window.removeEventListener('recopile:license',h); },[]);
  useEffect(() => {
    if(!boot || boot.app_notice?.required)return;
    for(const p of boot.pending_updates||[]) {
      if(!p.notify_only || !p.documents || notifiedUpdates.current.has(p.documents.fingerprint))continue;
      notifiedUpdates.current.add(p.documents.fingerprint);
      notice(boot.settings.auto_update ? `Nowa wersja gry: ${p.name} · ${p.version}. Aktualizacja przy kolejnym starcie.` : `Nowa wersja gry: ${p.name} · ${p.version}. Automatyczne aktualizacje są wyłączone.`);
      invoke('/api/review-seen',{fingerprint:p.documents.fingerprint});
    }
  },[boot?.pending_updates,boot?.app_notice?.required]);
  useEffect(() => {
    const open=path=>{setPendingPackage(path);setNav('workshop');setDetail(null);setAdd(false);};
    const unsubscribe=window.recopile?.onModPackage?.(open);
    window.recopile?.getModPackage?.().then(path=>{if(path)open(path);}).catch(()=>{});
    return ()=>unsubscribe?.();
  },[]);
  useEffect(() => {
    if (!boot) return; let live = true;
    const poll = async () => { try { const data = await json('/api/status'); if (!live) return; setOnline(true); setBoot(b => ({ ...b, ...data })); const s = data.jobs.map(j => j.id + ':' + j.status).join('|') + ':' + data.media_revision; if (signature.current !== s) { signature.current = s; setRevision(v => v + 1); } } catch { if (live) setOnline(false); } };
    const interval = setInterval(poll, 2000); return () => { live = false; clearInterval(interval); };
  }, [Boolean(boot)]);
  useEffect(() => {
    if (!boot || !catalogPage) return; const controller = new AbortController(); setLoading(true);
    let view = nav === 'library' ? 'library' : nav === 'device' ? 'device' : nav === 'other' ? 'other' : 'catalog';
    if (tab === 'installed') view = 'installed'; else if (tab === 'library') view = 'library';
    const params = new URLSearchParams({ q: debounced, platform: nav === 'other' ? 'other' : platform, mode: nav === 'recompile' ? 'recompile' : 'all', view, device:nav==='device'?'1':'0', sort, limit: '12', offset: String(offset) });
    json('/api/games?' + params, { signal: controller.signal }).then(data => { setResult(data); if(data.games.length) requestMedia(data.games.map(g=>g.id),Boolean(debounced.trim())).catch(()=>{}); }).catch(e => { if (e.name !== 'AbortError') notice(e.message, true); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [Boolean(boot), nav, platform, tab, sort, debounced, offset, revision]);
  useEffect(() => { if (!detail) return; const controller=new AbortController(); json('/api/games/' + detail.id,{signal:controller.signal}).then(setDetail).catch(() => {}); return ()=>controller.abort(); }, [revision,detail?.id]);
  useEffect(() => {
    if (!boot || boot.app_notice?.required || boot.app_notice?.updated || review || detail || add) return;
    const all = [...(boot.pending_updates || []), ...(boot.launcher_update?.available && boot.launcher_update.documents ? [{...boot.launcher_update,source_id:'launcher',target:'launcher'}] : [])];
    const pending = all.find(p => p.documents && !p.notify_only && !shownUpdates.current.has(p.documents.fingerprint));
    if (pending) { shownUpdates.current.add(pending.documents.fingerprint); setReview({ documents:pending.documents, source_id:pending.source_id, game_id:pending.target, automatic:true }); }
  }, [boot?.pending_updates, boot?.launcher_update, boot?.app_notice, Boolean(review), Boolean(detail), add]);
  if (!boot) return <div className="startup"><GameController size={40} /><h1>RE:<span>COPILE</span></h1>{online ? <><Spinner /><p>Otwieranie Twojej biblioteki…</p></> : <><p>Nie udało się połączyć z lokalnym launcherem.</p><button className="primary" onClick={() => refresh().catch(() => {})}>Spróbuj ponownie</button></>}</div>;
  const jobs = boot.jobs || [], currentJob = [...jobs].reverse().find(activeJob), pending = jobs.filter(activeJob).length;
  const menu = [['catalog', Books, 'Biblioteka', null], ['library', Heart, 'Moje gry', boot.stats.library], ['device', Monitor, boot.host.system==='Android' ? 'Na tym urządzeniu' : 'Na tym PC', null], ['discover', Compass, 'Odkrywaj', null], ['recompile', Lightning, 'Rekompilacje', boot.stats.recompiled], ['downloads', DownloadSimple, 'Pobieranie', pending || boot.pending_updates?.length || null]];
  const headings = {
    catalog: ['Biblioteka gier', `${count(boot.stats.total)} pozycji w katalogu · ${count(boot.stats.installed)} twoich instalacji`],
    library: ['Moje gry', 'Twoje porty, własne kopie i lokalne gry.'], discover: ['Odkrywaj', 'Znajdź powód, by wrócić do ulubionej konsoli.'],
    device: [boot.host.system==='Android' ? 'Na tym urządzeniu' : 'Na tym PC', boot.host.system==='Linux' ? 'Paczki Linux, lokalne gry i opcje Windows przez Proton / Wine. Dostępność paczki nie potwierdza działania gry.' : boot.host.system==='Windows' ? 'Paczki Windows i lokalne gry. Dostępność paczki nie potwierdza działania gry.' : 'Paczki dla tego urządzenia. Zgodność sprawdź w raportach.'],
    recompile: ['Rekompilacje', 'Gry z przypisanym projektem portu. Bez emulacji konsoli.'], other: ['Inne gry', 'Twoje projekty i gry spoza konsolowego katalogu.'],
    downloads: ['Pobieranie', 'Instalacje i aktualizacje, w jednym miejscu.'], sources: ['Źródła gier', 'Projekty, które śledzi Twoja biblioteka.'],
    engines: ['Emulatory', 'Wybierz sposób uruchamiania własnych kopii.'], tools: ['Jak grać', 'Instrukcje przygotowania własnej kopii i narzędzia płyt.'], settings: ['Ustawienia', 'Twój launcher, na Twoich zasadach.'], profile: ['Twój profil', 'Twoje gry i historie, zapisane na urządzeniu.'],
    collections:['Kolekcje','Wszystkie części serii w jednym miejscu.'],workshop:['Workshop','Mody społeczności i szablony dla twórców.'],
    performance:['Pomiary','Sprzęt, FPS i ustawienia Twoich sesji testowych.'],
  };
  const [heading, subheading] = headings[nav];
  return <div className="app-shell">
    <aside className="sidebar"><button className="brand" onClick={() => go('catalog')} aria-label="Recopile — biblioteka">RE:<span>COPILE</span><small>GAMES HUB</small></button>
      <nav className="main-nav" aria-label="Nawigacja główna">{menu.map(([key, Icon, label, number]) => <button key={key} className={nav === key ? 'active' : ''} onClick={() => go(key)}><Icon size={20} weight={nav === key ? 'fill' : 'regular'} /><span>{label}</span>{number !== null && <span className="nav-count">{number}</span>}</button>)}</nav>
      <div className="nav-heading">PLATFORMY</div><nav className="platform-nav" aria-label="Platformy">{[['all', SquaresFour], ['xbox360', GameController], ['xboxone', GameController], ['ps2', GameController], ['ps3', GameController], ['other', Monitor]].map(([key, Icon]) => <button key={key} onClick={() => { if (key === 'other') { setPlatform('all'); go('other'); } else selectPlatform(key); }} className={(platform === key && catalogPage && nav !== 'other') || (key === 'other' && nav === 'other') ? 'selected' : ''}><Icon size={19} className={'platform-icon ' + key} /><span>{platforms[key]}</span>{key !== 'all' && <small>{count(boot.stats.platforms[key])}</small>}</button>)}</nav>
      <div className="nav-heading tools-heading">TWOJA BIBLIOTEKA</div><nav className="main-nav compact">{[['collections', Books, 'Kolekcje'], ['workshop', Wrench, 'Workshop'], ['engines', Cpu, 'Emulatory'], ['sources', GithubLogo, 'Źródła'], ['tools', Books, 'Jak grać'], ['performance', Cpu, 'Pomiary']].map(([key, Icon, label]) => <button key={key} className={nav === key ? 'active' : ''} onClick={() => go(key)}><Icon size={19} /><span>{label}</span></button>)}</nav>
      <div className="sidebar-bottom"><button className="add-game outline" onClick={() => setAdd(true)}><Plus size={18} />Dodaj grę lub źródło</button><button className={'settings-nav ' + (nav === 'settings' ? 'selected' : '')} onClick={() => go('settings')}><GearSix size={20} />Ustawienia</button><button className="profile" onClick={() => go('profile')} aria-label="Otwórz profil"><div className="profile-icon"><UserCircle size={34} weight="duotone" /><span className="status-dot" /></div><div><strong translate="no">{boot.profile.profile.name}</strong><small>Profil lokalny</small></div><Badge kind="muted">v{boot.version}</Badge></button></div>
    </aside>
    <div className="workspace"><header className="topbar"><div className="search-field"><MagnifyingGlass size={19} /><input ref={search} aria-label="Szukaj gry w katalogu" placeholder="Szukaj gry, tytułu lub numeru płyty…" value={query} onChange={e => { setQuery(e.target.value); if (!catalogPage) go('catalog'); }} />{query ? <button className="icon-button" aria-label="Wyczyść wyszukiwanie" onClick={() => setQuery('')}><X size={16} /></button> : <kbd>Ctrl K</kbd>}</div><div className="select-wrap platform-select"><select aria-label="Filtr platformy" value={nav === 'other' ? 'other' : platform} onChange={e => selectPlatform(e.target.value)}>{Object.entries(platforms).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><CaretDown size={13} /></div><LanguageSelect compact value={boot.settings.language} onChange={changeLanguage}/><button className="icon-button notification" aria-label="Aktualizacje i powiadomienia" onClick={() => go('downloads')}><Bell size={22} />{(pending > 0 || boot.pending_updates?.length>0) && <span className="notification-dot" />}</button></header>
      {!online && <div className="connection-error"><WarningCircle size={18} />Brak połączenia z lokalnym serwisem. Próba ponownego połączenia trwa…</div>}
      <div className="content-with-rail"><main className="main-content"><div className="page-heading"><div><h1>{heading}{nav === 'recompile' && <Lightning weight="fill" />}</h1><p>{subheading}</p></div>{catalogPage && <button className="outline add-small" onClick={() => setAdd(true)}><Plus size={17} /><span>Dodaj grę</span></button>}</div>
        {catalogPage ? <><div className="library-controls"><div className="tabs" role="tablist" aria-label="Widok biblioteki">{[['all', 'Wszystkie'], ['installed', 'Zainstalowane'], ['library', 'W bibliotece']].map(([key, label]) => <button role="tab" aria-selected={tab === key} className={tab === key ? 'active' : ''} key={key} onClick={() => { setTab(key); setOffset(0); }}>{label}</button>)}</div><div className="sort-controls"><div className="select-wrap"><select aria-label="Sortuj gry" value={sort} onChange={e => { setSort(e.target.value); setOffset(0); }}><option value="featured">Polecana kolejność</option><option value="title">Nazwa A–Z</option><option value="platform">Platforma</option></select><CaretDown size={12} /></div><button className="icon-button" aria-label={layout === 'grid' ? 'Widok listy' : 'Widok siatki'} onClick={() => setLayout(l => l === 'grid' ? 'list' : 'grid')}>{layout === 'grid' ? <List size={20} /> : <SquaresFour size={20} />}</button></div></div>
          <div className="mode-filter"><div><Toggle small value={boot.settings.only_recompiled} onChange={v => { invoke('/api/settings', { only_recompiled: v }); setOffset(0); }} label="Tylko rekompilacje" /><span>Tylko rekompilacje</span><span className="mode-hint">Graj natywnie</span></div><span>{loading ? <Spinner /> : `${count(result.total)} wyników`}</span></div>
          <div className="cover-controls"><span>Okładki pobierają się dla wyników wyszukiwania lub na żądanie. Opisy są dostępne niezależnie.</span><button className="outline" disabled={loading || requestingCovers || !result.games.length} onClick={()=>downloadCovers(result.games.map(g=>g.id))} title="Pobierz okładki dla widocznych gier"><DownloadSimple size={15}/>Pobierz okładki</button></div>
          {result.games.length ? <div className={`games ${layout}`} aria-busy={loading}>{result.games.map(game => <GameCard key={game.id} game={game} jobs={jobs} running={boot.running} host={boot.host} onOpen={() => openGame(game.id)} />)}</div> : !loading ? <Empty title={query ? 'Nie znaleziono gry' : 'Tu zaczyna się Twoja biblioteka'} text={query ? 'Spróbuj innej nazwy lub platformy. Możesz też dodać własny wpis i źródło.' : boot.settings.only_recompiled ? 'W tym widoku nie ma przypisanych rekompilacji. Zmień platformę lub dodaj projekt portu.' : 'Dodaj własną kopię gry albo zainstaluj dostępny port.'}><button className="primary" onClick={() => { if (tab !== 'all' || nav === 'library') { setTab('all'); go('catalog'); } else setAdd(true); }}><Plus size={17} />{tab !== 'all' || nav === 'library' ? 'Przejdź do katalogu' : 'Dodaj grę'}</button></Empty> : <div className="loading-line"><Spinner />Wyszukiwanie w katalogu…</div>}
          {result.total > 12 && <div className="pagination"><button className="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 12))}>Poprzednie</button><span>{count(offset + 1)}–{count(Math.min(offset + 12, result.total))} z {count(result.total)}</span><button className="outline" disabled={offset + 12 >= result.total} onClick={() => setOffset(offset + 12)}>Następne<ArrowRight size={15} /></button></div>}<div className="catalog-note"><Database size={14} />Katalog metadanych Libretro / Wikipedia · Statusy portów mają osobne źródła · Zgodność gry sprawdź w projekcie</div>
        </> : nav === 'downloads' ? <Downloads boot={boot} invoke={invoke} /> : nav === 'sources' ? <Sources boot={boot} invoke={invoke} action={action} onEdit={setEditSource} onManual={setManualSource} onAdd={() => setAdd(true)} /> : nav === 'engines' ? <Engines boot={boot} invoke={invoke} go={go} /> : nav === 'tools' ? <Tools invoke={invoke} onAdd={() => setAdd(true)} go={go} /> : nav === 'profile' ? <ProfilePage boot={boot} action={action} invoke={invoke} onOpen={openGame}/> : nav === 'collections' ? <Collections boot={boot} go={go} onOpen={openGame} action={action} invoke={invoke} onAdd={setAdd} onRequestCovers={ids=>requestMedia(ids,true).catch(()=>{})}/> : nav === 'workshop' ? <WorkshopPage boot={boot} action={action} invoke={invoke} pendingPackage={pendingPackage} onPackageHandled={()=>setPendingPackage(null)}/> : nav === 'performance' ? <PerformancePage boot={boot} action={action}/> : <Settings boot={boot} action={action} invoke={invoke} />}
      </main><aside className="right-rail"><div className="rail-heading"><h2>Śledzone projekty</h2><span>{boot.sources.length} źródeł</span></div><div className="tracked-projects">{boot.sources.filter(s => ['pinyon', 'skate3', 'unleashed'].includes(s.id)).map(s => <button key={s.id} onClick={() => go('sources')} className="tracked-project"><div className="project-avatar"><GithubLogo size={23} weight="duotone" /></div><div><strong>{s.name}</strong><small className={s.release ? 'green' : ''}>{s.release?.version || 'GitHub Releases'}</small></div><span className="project-dot" /></button>)}</div><button className="outline rail-add" onClick={() => setAdd(true)}><Plus size={16} />Dodaj źródło</button><div className="rail-divider" />
        <section className="rail-card native-card"><div className="card-kicker">NOWE ŻYCIE KLASYKÓW</div><div className="native-icon"><Lightning size={38} weight="duotone" /></div><h3>Natywnie na Twoim PC.</h3><p>Sprawdzone projekty portów, w jednej bibliotece.</p><div className="native-count"><strong>{boot.stats.recompiled}</strong><span>tytuły z rekompilacją</span></div><button className="text-link" onClick={() => { setPlatform('all'); go('recompile'); }}>Zobacz rekompilacje<ArrowRight size={15} /></button></section>
        <section className="rail-card ownership-card"><ShieldCheck size={24} /><h3>Twoja kopia. Twoja gra.</h3><p>Port dostarcza program. Dane gry importujesz z własnej płyty lub kopii.</p><button className="text-link" onClick={() => go('tools')}>Jak zacząć<ArrowRight size={15} /></button></section><a href={sponsor} target="_blank" rel="noopener noreferrer" className="rail-support"><Heart size={17}/>Wesprzyj rozwój Recopile</a><div className="rail-bottom"><HardDrives size={18} /><div><strong>{bytes(boot.libraries?.find(l => l.default)?.free || 0)} wolnego</strong><button onClick={() => go('settings')}>Zarządzaj bibliotekami</button></div></div>
      </aside></div>
    </div>
    <footer className={`download-footer ${currentJob ? 'downloading' : ''}`}><button className="footer-task" onClick={() => go('downloads')}>{currentJob ? <><DownloadSimple size={21} /><div><strong>{currentJob.title}</strong><span>{currentJob.message}{currentJob.total > 0 && ` · ${bytes(currentJob.downloaded)} / ${bytes(currentJob.total)}`}</span></div></> : <><CheckCircle size={20} weight="duotone" /><div><strong>{boot.pending_updates?.length ? `${boot.pending_updates.length} aktualizacji po restarcie` : 'Biblioteka jest gotowa'}</strong><span>{boot.running?.length ? `${boot.running[0].title} · uruchomiona` : 'Twoje gry, w jednym miejscu.'}</span></div></>}</button>{currentJob ? <><div className="footer-progress"><div><span style={{ width: currentJob.progress + '%' }} /></div><small>{Math.round(currentJob.progress)}%</small></div><button className="icon-button" aria-label="Anuluj bieżące zadanie" onClick={() => invoke('/api/cancel', { job_id: currentJob.id })}><X size={18} /></button></> : <div className="footer-status"><span className={`status-dot ${!online ? 'offline' : ''}`} />{online ? 'Połączenie lokalne' : 'Brak połączenia'}<span className="footer-sep" />{boot.host.system} · v{boot.version}</div>}</footer>
    {detail && <GameDetail game={detail} boot={boot} action={action} invoke={invoke} onClose={() => setDetail(null)} openGame={openGame} go={go} onEdit={setEditSource} onManual={setManualSource} onCovers={downloadCovers} requestingCovers={requestingCovers} />}{add && <AddGame initialGame={typeof add==='object'?add:null} boot={boot} action={action} onClose={() => setAdd(false)} onAdded={id => { setAdd(false); go('library'); openGame(id); }} />}
    {review && <ProjectReview key={review.documents.fingerprint} review={review} boot={boot} action={action} onClose={() => setReview(null)}/>}
    {launchChoice && <LaunchOptionsDialog choice={launchChoice} action={action} onClose={()=>setLaunchChoice(null)}/>}
    {editSource && <SourceEditor source={editSource} action={action} onClose={() => setEditSource(null)}/>}
    {manualSource && <ManualSource source={manualSource} invoke={invoke} onClose={() => setManualSource(null)}/>}
    {(showLicense || boot.app_notice?.required || boot.app_notice?.updated) && <AppNotice boot={boot} action={action} onFinish={() => setShowLicense(false)}/>}
    {toast && <div className={`toast ${toast.error ? 'error' : ''}`} role={toast.error ? 'alert' : 'status'}>{toast.error ? <WarningCircle size={20} /> : <CheckCircle size={20} />}<span>{toast.text}</span><button className="icon-button" aria-label="Zamknij powiadomienie" onClick={() => setToast(null)}><X size={16} /></button></div>}
  </div>;
}

function GameCard({ game, jobs, running, host, onOpen }) {
  const job = jobs.find(j => j.target === game.id && activeJob(j)), playing = running?.some(r => r.id === game.id), install = game.install, steam = install?.adapter==='steam' && !install?.local_executable, primary = game.kind === 'recompile';
  const label = job ? 'W kolejce…' : playing ? 'Uruchomiona' : install?.ready ? steam?'Uruchom w Steam':'Graj' : game.steam_app_id && !game.steam_detected ? 'Instalacja niedostępna' : install?.executable || install?.command ? 'Przygotuj grę' : game.development_status ? 'Zobacz projekt' : primary ? game.device_options?.some(o=>o.via==='native') ? 'Zainstaluj port' : 'Zobacz opcje' : install?.data_path ? 'Otwórz grę' : game.kind === 'catalog' ? 'Zobacz opis' : game.kind === 'native' ? 'Dodaj instalację' : 'Dodaj swoją kopię';
  return <article className={`game-card ${primary ? 'native' : ''}`}><div className="game-platform"><GameController size={13} weight="duotone" className={game.platform} /><span>{platforms[game.platform]}</span>{game.added && <Check size={12} aria-label="W bibliotece" />}</div><button className="cover-button" onClick={onOpen} aria-label={`Otwórz ${game.title}`}><Cover game={game} /><span className={`cover-badge ${game.kind}`}><span />{game.steam_app_id ? 'Steam' : game.development_status === 'in_progress' ? 'Rekompilacja w trakcie' : game.development_status === 'planned' ? 'Port planowany' : modes[game.kind]}</span><span className="cover-open"><ArrowRight size={20} /></span></button><div className="game-info"><button className="game-title" translate="no" onClick={onOpen}>{game.title}</button><div className="game-meta"><span>{game.year || 'Katalog'}</span><span className="tiny-dot" /><span>{game.steam_app_id && game.steam_detected ? 'Wykryto w Steam' : install?.ready ? 'Gotowa do gry' : primary ? game.device_options?.some(o=>o.via==='native') ? `Port · ${host.system}` : game.device_options?.length ? 'Windows · Proton / Wine' : 'Brak paczki na ten PC' : game.kind === 'catalog' ? 'Brak integracji' : game.kind === 'native' ? 'Twój projekt' : 'Przez emulator'}</span></div>{game.sources?.some(s=>s.edition==='recopile') && <Badge kind="recompile">RE:COPILE Edition</Badge>}{primary && <PlatformBadges source={game.sources?.[0]}/>}<DeviceBadges game={game}/><TechnologyBadges game={game}/><div className={'device-badge '+(game.compatibility?.status || 'unknown')} title={game.compatibility?.support}><Monitor size={12}/><span>{game.compatibility?.label || 'Brak raportu urządzenia'}</span></div><button className={`game-action ${primary || install?.ready ? 'primary' : 'secondary'}`} onClick={onOpen} disabled={Boolean(job)}>{job ? <Spinner /> : install?.ready ? <Play size={14} weight="fill" /> : primary ? <DownloadSimple size={15} /> : <Plus size={15} />}{label}</button></div></article>;
}
