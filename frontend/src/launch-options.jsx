import React, {useState} from 'react';
import {Play, Wrench} from '@phosphor-icons/react';
import {Modal, Spinner} from './ui.jsx';

export function LaunchOptionsDialog({choice, action, onClose}) {
  const [remember,setRemember]=useState(choice.preferred!=='ask');
  const [busy,setBusy]=useState(false);
  async function launch(mode) {
    setBusy(true);
    try {
      const result=await action('/api/launch',{
        ...choice.request,game_id:choice.game_id,launch_mode:mode,remember,
      },mode==='launcher'?'Otwieranie launchera Pinyon Shift…':'Uruchamianie gry…');
      if(!result.launch_choice_required)onClose();
    } catch {} finally {setBusy(false);}
  }
  return <Modal title="Jak uruchomić grę?" subtitle={choice.title} onClose={onClose} dismissible={!busy}>
    <p>Graj od razu albo otwórz oryginalny launcher Pinyon Shift, aby zmienić ustawienia.</p>
    <div className="port-setup-actions">
      <button type="button" className="primary" disabled={busy} onClick={()=>launch('game')}>{busy?<Spinner/>:<Play size={18}/>}Graj od razu</button>
      <button type="button" className="outline" disabled={busy || !choice.launcher_available} onClick={()=>launch('launcher')}><Wrench size={18}/>Oryginalny launcher Pinyon Shift</button>
    </div>
    {!choice.launcher_available && <p className="form-help">Zaktualizuj narzędzia Pinyon Shift, aby pobrać oryginalny launcher dla tego systemu.</p>}
    <label className="checkbox-label"><input type="checkbox" checked={remember} disabled={busy} onChange={event=>setRemember(event.target.checked)}/>Zapamiętaj mój wybór</label>
    <p className="form-help">Wybór zmienisz w szczegółach gry, w Opcjach uruchamiania.</p>
  </Modal>;
}
