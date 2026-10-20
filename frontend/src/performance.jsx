import React, {useEffect, useState} from 'react';
import {ChartLine, Cpu, DownloadSimple, FolderOpen, Play, Stop, ArrowClockwise} from '@phosphor-icons/react';
import {Badge, Empty, External, Spinner, ago} from './ui.jsx';

export function saveJSON(value,filename) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export function Hardware({value}) {
  if(!value)return null;
  return <dl className="hardware-grid">{[['System',value.system],['CPU',value.cpu],['GPU',value.gpu],['RAM',value.ram_gb==null?'—':value.ram_gb+' GB'],['VRAM',value.gpu_memory_gb==null?'—':value.gpu_memory_gb+' GB'],['Sterownik',value.driver||'—']].map(([label,v])=><div key={label}><dt>{label}</dt><dd translate="no">{v||'—'}</dd></div>)}</dl>;
}

export function Measurement({report}) {
  const m=report.metrics;
  if(!m)return <p className="form-help">{report.error || 'Pomiar w toku…'}</p>;
  const points=m.series||[],max=Math.max(1,...points.map(p=>p.fps));
  return <div className="measurement-result">
    <div className="measurement-metrics">{[['Średnie FPS',m.average_fps],['1% low FPS',m.one_percent_low_fps??'—'],['P99 klatki',m.p99_frametime_ms+' ms'],['Czas nagrania',m.duration_seconds==null?'—':m.duration_seconds+' s']].map(([label,value])=><div key={label}><strong translate="no">{value}</strong><small>{label}</small></div>)}</div>
    {points.length>1 && <svg className="fps-chart" viewBox="0 0 600 110" role="img" aria-label="Przebieg FPS"><line x1="0" y1="105" x2="600" y2="105" stroke="#59436d"/><polyline points={points.map((p,i)=>`${i/(points.length-1)*600},${100-p.fps/max*90}`).join(' ')} fill="none" stroke="#c4a0ff" strokeWidth="2"/><text x="5" y="15" fill="#b6a3cc" fontSize="10">{Math.round(max)} FPS</text></svg>}
    <p className="form-help">{m.basis==='per_frame'?'Statystyki z czasów poszczególnych klatek.':'Próbkowane FPS; 1% low jest niedostępne.'} {m.samples} próbek · {m.recorder} · {report.port_version}</p>
    <p className="form-help" translate="no">{Object.values(report.settings||{}).filter(Boolean).join(' · ')}</p>
    <Hardware value={report.hardware}/>
  </div>;
}

export function PerformancePage({boot,action}) {
  const [state,setState]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [form,setForm]=useState({game_id:'',duration:60,warmup:5,resolution:'',preset:'',api:'',upscaling:'',notes:'',recorder_path:''});
  const [path,setPath]=useState(''),[stream,setStream]=useState(''),[streams,setStreams]=useState([]),[confirmed,setConfirmed]=useState(false);
  const [importHardware,setImportHardware]=useState({system:boot.host.system,cpu:'',gpu:'',ram_gb:'',driver:''});
  const [importVersion,setImportVersion]=useState('');
  async function load(){const r=await fetch('/api/performance');const value=await r.json();if(!r.ok)throw new Error(value.error);setState(value);}
  useEffect(()=>{let live=true;const refresh=()=>{if(live)load().catch(e=>setError(e.message));};refresh();const t=setInterval(refresh,2000);return()=>{live=false;clearInterval(t);};},[]);
  async function run(url,body){setBusy(true);setError('');try{const r=await action(url,body);await load();return r;}catch(e){setError(e.message);return null;}finally{setBusy(false);}}
  const set=(key,value)=>setForm(f=>({...f,[key]:value}));
  if(!state)return <div className="loading-line"><Spinner/>{error||'Wczytywanie pomiarów…'}</div>;
  const active=state.sessions.some(s=>['starting','recording','finishing'].includes(s.status));
  async function collect(){const r=await run('/api/performance/hardware',{});if(r)setImportHardware(r);}
  async function pick(){const r=await run('/api/pick',{});if(r?.path){setPath(r.path);setStreams([]);setStream('');}}
  async function importLog(){const r=await run('/api/performance/import',{...form,path,stream:stream||undefined,hardware:importHardware,port_version:importVersion});if(r?.selection_required)setStreams(r.streams);else if(r){setStreams([]);setStream('');}}
  return <div className="performance-page">
    <section className="panel"><div className="form-section-title"><h2><Cpu size={21}/>Sprzęt tego komputera</h2><button className="outline" disabled={busy} onClick={collect}><ArrowClockwise size={16}/>Odczytaj sprzęt</button></div><p className="form-help">Zapis lokalny: CPU, GPU, RAM, system i dostępny sterownik. Wybierasz, który raport udostępnić.</p><Hardware value={state.hardware}/></section>
    <section className="panel"><h2><ChartLine size={21}/>Nowy pomiar gry</h2><div className="tool-form">
      <label>Gra do pomiaru<select value={form.game_id} onChange={e=>set('game_id',e.target.value)}><option value="">Wybierz grę</option>{state.games.map(g=><option key={g.id} value={g.id}>{g.title}{!g.direct?' · import CSV':''}</option>)}</select></label>
      {!state.games.length && <p className="form-help">Podłącz lokalną instalację gry, aby uruchomić pomiar.</p>}
      <div className="form-columns"><label>Czas pomiaru (s)<input type="number" min="1" max="7200" value={form.duration} onChange={e=>set('duration',Number(e.target.value))}/></label><label>Rozgrzewka (s)<input type="number" min="1" max="600" value={form.warmup} onChange={e=>set('warmup',Number(e.target.value))}/></label></div>
      <div className="form-columns"><label>Rozdzielczość<input value={form.resolution} maxLength="80" placeholder="1920 × 1080" onChange={e=>set('resolution',e.target.value)}/></label><label>Ustawienia grafiki<input value={form.preset} maxLength="80" placeholder="High / własne" onChange={e=>set('preset',e.target.value)}/></label></div>
      <div className="form-columns"><label>API grafiki<input value={form.api} maxLength="80" placeholder="Vulkan / DirectX 12" onChange={e=>set('api',e.target.value)}/></label><label>Upscaling / generowanie klatek<input value={form.upscaling} maxLength="100" placeholder="Wyłączone / FSR Quality…" onChange={e=>set('upscaling',e.target.value)}/></label></div>
      <label>Scena testowa i uwagi<textarea value={form.notes} rows="3" maxLength="2000" onChange={e=>set('notes',e.target.value)}/></label>
      {boot.host.system==='Windows' && <label>Program PresentMon<input value={form.recorder_path} placeholder="C:\\Tools\\PresentMon.exe" onChange={e=>set('recorder_path',e.target.value)}/></label>}
      <p className="form-help">Ustawienia wpisujesz zgodnie z grą. Nagrywanie kończy się po wybranym czasie; gra pozostaje uruchomiona. Dla Steam / Flatpak użyj importu logu.</p>
      <div className="tool-actions"><button className="primary" disabled={busy||active||!form.game_id||!state.games.find(g=>g.id===form.game_id)?.direct} onClick={()=>run('/api/performance/start',form)}>{busy?<Spinner/>:<Play size={17}/>}Uruchom grę i pomiar</button><External className="text-link" href={boot.host.system==='Windows'?'https://github.com/GameTechDev/PresentMon':'https://github.com/flightlessmango/MangoHud'}>{boot.host.system==='Windows'?'PresentMon':'MangoHud'}</External>{boot.host.system==='Linux'&&!state.mangohud&&<Badge kind="warning">MangoHud nie jest zainstalowany</Badge>}</div>
    </div></section>
    <details className="panel import-measurement"><summary>Importuj pomiar MangoHud / PresentMon (CSV)</summary><div className="tool-form"><label>Plik CSV<div className="path-field"><input value={path} onChange={e=>{setPath(e.target.value);setStreams([]);setStream('');}}/><button type="button" className="outline" onClick={pick}><FolderOpen size={18}/></button></div></label>
      <p className="form-help">Wybierz powyżej grę. Podaj sprzęt z nagrania; log może pochodzić z innego komputera.</p>
      <button className="text-link" onClick={collect}>Użyj sprzętu tego komputera</button>
      {['system','cpu','gpu','ram_gb','driver'].map(key=><label key={key}>{({system:'System nagrania',cpu:'CPU',gpu:'GPU',ram_gb:'RAM (GB)',driver:'Sterownik'})[key]}<input value={importHardware[key]||''} onChange={e=>{setImportHardware(h=>({...h,[key]:e.target.value}));setConfirmed(false);}}/></label>)}
      <label>Wersja gry / portu<input value={importVersion} maxLength="100" onChange={e=>setImportVersion(e.target.value)}/></label>
      {streams.length>0 && <label>Proces / swapchain<select value={stream} onChange={e=>setStream(e.target.value)}><option value="">Wybierz strumień</option>{streams.map(s=><option key={s.id} value={s.id}>{s.id} · {s.samples}</option>)}</select></label>}
      <label className="checkbox-label"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Potwierdzam grę, sprzęt i ustawienia tego nagrania.</label><button className="outline" disabled={busy||!form.game_id||!path||!confirmed||(streams.length>0&&!stream)} onClick={importLog}>Importuj CSV</button>
    </div></details>
    {error&&<p className="source-error" role="alert">{error}</p>}
    <section className="panel"><h2>Historia pomiarów</h2>{!state.sessions.length?<Empty title="Brak pomiarów" text="Uruchom test lub zaimportuj log CSV."/>:state.sessions.map(s=><article className="benchmark-session" key={s.id}><div className="form-section-title"><div><h3 translate="no">{s.title}</h3><small>{ago(s.started_at)}</small></div><Badge kind={s.status==='complete'?'recompile':'muted'}>{({complete:'Zakończony',recording:'Nagrywanie',starting:'Uruchamianie',finishing:'Zapisywanie',no_data:'Brak próbek FPS',failed:'Błąd',interrupted:'Przerwano'})[s.status]||s.status}</Badge></div><Measurement report={s}/>{s.status==='recording'&&<button className="outline" disabled={busy} onClick={()=>run('/api/performance/stop',{session_id:s.id})}><Stop size={16}/>Zakończ pomiar</button>}{s.status==='complete'&&<button className="outline" onClick={async()=>{const r=await run('/api/performance/export',{session_id:s.id});if(r)saveJSON(r,'recopile-measurement.json');}}><DownloadSimple size={16}/>Eksportuj raport</button>}</article>)}</section>
  </div>;
}
