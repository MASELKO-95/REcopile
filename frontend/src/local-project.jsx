import React, {useState} from 'react';
import {Check, FolderOpen, X} from '@phosphor-icons/react';
import {Spinner} from './ui.jsx';

export function LocalRatchetPanel({game,action,onSaved,onClose}) {
  const [root,setRoot]=useState(game.local_project?.root || ''),[trusted,setTrusted]=useState(false),[busy,setBusy]=useState(false);
  async function browse() {setBusy(true);try{const result=await action('/api/pick',{mode:'folder'});if(result.path)setRoot(result.path);}catch{}finally{setBusy(false);}}
  async function submit(e) {
    e.preventDefault();setBusy(true);
    try {await action('/api/project/local',{source_id:'ratchet3-local',root,trusted},'Połączono lokalny projekt RE:COPILE Edition. Rozgrywka pozostaje niepotwierdzona.');await onSaved();onClose();}
    catch{}finally{setBusy(false);}
  }
  return <form className="import-form" onSubmit={submit}>
    <div className="form-section-title"><strong>Up Your Arsenal (Ratchet 3) · RE:COPILE Edition</strong><button type="button" className="icon-button" aria-label="Zamknij formularz" onClick={onClose}><X size={16}/></button></div>
    <p className="form-help">Podłącz folder projektu z lokalną kompilacją Linux i własnymi danymi gry. Uruchomienie korzysta z tools/run-native.sh. Projekt pozostaje w swoim folderze; nie jest kopiowany ani publikowany.</p>
    <label className="field-label" htmlFor="ratchet-project-root">Folder zbudowanego projektu</label><div className="inline-field"><input id="ratchet-project-root" required value={root} onChange={e=>setRoot(e.target.value)}/><button type="button" className="outline" disabled={busy} onClick={browse}><FolderOpen size={17}/>Wybierz folder</button></div>
    <label className="checkbox-label"><input type="checkbox" required checked={trusted} onChange={e=>setTrusted(e.target.checked)}/>Ufam temu lokalnemu projektowi i chcę uruchamiać jego eksperymentalny program.</label>
    <p className="form-help">Potwierdzono jedynie postęp do intro i ekranu tytułowego. Pełna rozgrywka oraz Windows pozostają niepotwierdzone.</p>
    <button className="primary" disabled={busy || !trusted || !root.trim()}>{busy?<Spinner/>:<Check size={17}/>}Podłącz projekt</button>
  </form>;
}
