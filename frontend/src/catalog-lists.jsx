// Public project list tracking. Copyright (C) 2026 MASELKO-95. GPL-3.0-only.
import React, {useEffect, useState} from 'react';
import {ArrowClockwise, Books, CheckCircle, Plus} from '@phosphor-icons/react';
import {Badge, External, Spinner, ago, activeJob} from './ui.jsx';
import './catalog-lists.css';

export function CatalogLists({boot, action, onOpen}) {
  const [data,setData]=useState(null),[query,setQuery]=useState(''),[page,setPage]=useState(0),[error,setError]=useState('');
  const revision=JSON.stringify(boot.catalog_lists);
  useEffect(()=>{
    const controller=new AbortController();
    fetch('/api/catalog-lists',{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error('Nie udało się odczytać list projektów.');return r.json();})
      .then(value=>{setData(value);setError('');}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return ()=>controller.abort();
  },[revision]);
  const busy=boot.jobs.some(j=>activeJob(j)&&['catalog-lists','check'].includes(j.kind));
  const lists=data?.lists || boot.catalog_lists?.lists || [];
  const entries=[...new Map(lists.flatMap(list=>(list.entries || []).map(entry=>({...entry,list_id:list.id}))).map(e=>[e.repo.toLowerCase(),e])).values()];
  const filtered=entries.filter(e=>(e.title+' '+e.repo).toLowerCase().includes(query.toLowerCase()));
  async function add(entry) {
    try {const result=await action('/api/catalog-lists/include',{list_id:entry.list_id,repo:entry.repo},'Dodano grę do katalogu.');if(result.game_id)onOpen(result.game_id);}catch{}
  }
  return <section className="panel catalog-lists" aria-labelledby="catalog-lists-title">
    <div className="panel-title"><Books size={25}/><div><h2 id="catalog-lists-title">Śledzone listy projektów</h2><p>Nowe gry i źródła pojawiają się automatycznie przy sprawdzaniu aktualizacji.</p></div></div>
    <div className="catalog-list-summaries">{lists.map(list=><div key={list.id}><External href={list.url}>{list.name}</External><span>{list.total} <span>projektów</span> · {list.total-list.missing} <span>w katalogu</span></span><small>{ago(list.checked_at)}</small>{list.error&&<p role="status" className="source-error">{list.error}</p>}</div>)}</div>
    <p className="form-help">Status „w katalogu” oznacza dodane źródło. Dostępność paczki i przygotowanie gry sprawdzisz w jej szczegółach.</p>
    {!boot.settings.track_catalog_lists&&<p className="form-help">Automatyczne śledzenie list jest wyłączone w ustawieniach.</p>}
    <button type="button" className="outline" disabled={busy} onClick={()=>action('/api/catalog-lists/check',{},'Sprawdzanie list projektów dodane do kolejki.').catch(()=>{})}>{busy?<Spinner/>:<ArrowClockwise size={17}/>}Sprawdź listy i dodaj nowe gry</button>
    {error&&<p role="alert">{error}</p>}
    <label className="catalog-list-search">Szukaj na śledzonych listach<input value={query} onChange={e=>{setQuery(e.target.value);setPage(0);}} type="search"/></label>
    <div className="catalog-list-entries">{filtered.slice(page*10,page*10+10).map(entry=><article key={entry.repo}><div><strong translate="no">{entry.title}</strong><External href={'https://github.com/'+entry.repo}>{entry.repo}</External></div><Badge kind={entry.game_id?'recompile':'muted'}>{entry.game_id?'W katalogu':'Nowe źródło'}</Badge><button type="button" className="text-link" onClick={()=>entry.game_id?onOpen(entry.game_id):add(entry)}>{entry.game_id?<CheckCircle size={16}/>:<Plus size={16}/ >}{entry.game_id?'Otwórz grę':'Dodaj grę'}</button></article>)}</div>
    {filtered.length>10&&<div className="pagination"><button type="button" className="outline" disabled={!page} onClick={()=>setPage(p=>p-1)}>Poprzednie</button><span>{Math.min(page*10+1,filtered.length)}–{Math.min(page*10+10,filtered.length)} / {filtered.length}</span><button type="button" className="outline" disabled={(page+1)*10>=filtered.length} onClick={()=>setPage(p=>p+1)}>Następne</button></div>}
  </section>;
}
