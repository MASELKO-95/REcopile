import React, {useState} from 'react';
import {Check, DownloadSimple, File, FolderOpen, Info, Wrench, X} from '@phosphor-icons/react';
import {activeJob, Badge, Spinner} from './ui.jsx';

export function PortSetupPanel({game,boot,action,invoke,onClose}) {
  const [path,setPath]=useState(game.port_setup?.input_path || ''),[owned,setOwned]=useState(false),[busy,setBusy]=useState(false);
  const jobs=boot.jobs.filter(j=>j.target===game.id && j.kind==='prepare');
  const job=jobs.find(activeJob) || jobs[0], working=Boolean(job && activeJob(job));
  async function browse(mode) {setBusy(true);try {const result=await action('/api/pick',{mode});if(result.path)setPath(result.path);}catch{}finally{setBusy(false);}}
  async function start(verify_only) {
    if(!owned || !path.trim())return;
    setBusy(true);
    try {await action('/api/port-setup',{game_id:game.id,path,owned,verify_only},'Przygotowanie dodane do kolejki RE:COPILE.');}
    catch{}finally{setBusy(false);}
  }
  return <section className="port-setup-panel" aria-label="Przygotowanie portu w RE:COPILE">
    <div className="form-section-title"><strong><Wrench size={17}/>Pinyon Shift</strong><button type="button" className="icon-button" aria-label="Zamknij formularz" onClick={onClose}><X size={16}/></button></div>
    <p>Wybierz własne ISO lub wypakowany folder Forza Horizon. Weryfikacja i budowanie korzystają z narzędzi Pinyon Shift, a postęp pozostaje w RE:COPILE.</p>
    <label className="field-label" htmlFor="port-input">Twoja kopia Forza Horizon</label><input id="port-input" value={path} disabled={working} onChange={e=>setPath(e.target.value)} placeholder="Ścieżka do własnego ISO lub folderu gry"/>
    <div className="browse-row"><button type="button" className="text-link" disabled={busy || working} onClick={()=>browse('file')}><File size={15}/>Wybierz ISO</button><button type="button" className="text-link" disabled={busy || working} onClick={()=>browse('folder')}><FolderOpen size={15}/>Wybierz folder</button></div>
    <label className="checkbox-label"><input type="checkbox" checked={owned} disabled={working} onChange={e=>setOwned(e.target.checked)}/>To moja kopia gry i mam prawo korzystać z tych plików.</label>
    <p className="form-help">Pierwsza kompilacja może pobrać kompilator i zależności oraz wymagać około 45 GB wolnego miejsca. Obsługiwane wydanie i wymagania sprawdź w README. Samo pobranie narzędzi nie przygotowuje gry.</p>
    <button type="button" className="text-link" onClick={()=>invoke('/api/project-info',{source_id:game.port_setup.source_id})}><Info size={15}/>README, licencja i wsparcie autorów</button>
    <div className="port-setup-actions"><button type="button" className="outline" disabled={busy || working || !owned || !path.trim()} onClick={()=>start(true)}><Check size={16}/>Sprawdź pliki</button><button type="button" className="primary" disabled={busy || working || !owned || !path.trim()} onClick={()=>start(false)}>{busy?<Spinner/>:<DownloadSimple size={17}/>}Sprawdź i zbuduj</button></div>
    {job && <div className={'port-setup-progress '+job.status} role="status"><div><Badge kind={job.status==='failed'?'warning':job.status==='completed'?'recompile':'muted'}>{working?'Przygotowanie w toku':job.status==='failed'?'Przygotowanie zatrzymane':job.status==='cancelled'?'Anulowano':'Zakończono zadanie'}</Badge>{working && <button type="button" className="text-link" onClick={()=>invoke('/api/cancel',{job_id:job.id})}>Anuluj</button>}</div><p>{job.result?.message || job.message}</p>{working && <><div className="progress-track"><span style={{width:job.progress+'%'}}/></div><small>{Math.round(job.progress)}%</small></>}{job.log && <details><summary>Log przygotowania</summary><code>{job.log}</code></details>}</div>}
    {game.port_setup?.ready && <p className="port-build-ready"><Check size={16}/>Lokalna kompilacja jest gotowa do uruchomienia. Ocena rozgrywki pozostaje osobnym raportem.</p>}
  </section>;
}
