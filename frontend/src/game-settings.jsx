import React, {useEffect, useRef, useState} from 'react';
import {ArrowCounterClockwise, Check, Cpu, X} from '@phosphor-icons/react';
import {Spinner} from './ui.jsx';
import {translate} from './i18n/index.js';

const names={bilinear:'Bilinear',cas:'CAS',fsr:'FSR 1',fsr2:'FSR 2',fsr3:'FSR 3',dlss:'DLSS',none:'Brak',fxaa:'FXAA',fxaa_extreme:'FXAA Extreme',vulkan:'Vulkan',custom:'Własne',ultra_low_30:'Ultra Low 30',low_spec_60:'Low-spec 60',balanced_40:'Balanced 40',performance_120:'Performance 120',quality_60:'Quality 60',shipping_1x:'1×',experimental_2x:'2×',experimental_3x:'3×',controller:'Pad','pc-camera':'Klawiatura i mysz — kamera','pc-steering':'Klawiatura i mysz — kierowanie'};
function valueName(key,value) {
  if(typeof value==='boolean')return translate(value?'Włączone':'Wyłączone');
  if(key==='resolution_scale')return value+'×';
  if(key==='anisotropy')return value===0?translate('Domyślne gry'):value+'×';
  if(key==='presentation_fps' && value===0)return translate('Bez limitu');
  return translate(names[value] || String(value));
}

export function GameSettingsPanel({game,boot,action,onClose}) {
  const panel=useRef(null);
  const [data,setData]=useState(null),[values,setValues]=useState({}),[changes,setChanges]=useState({});
  const [busy,setBusy]=useState(true),[error,setError]=useState(''),[hardware,setHardware]=useState(null),[saved,setSaved]=useState(false);
  const [argumentsText,setArgumentsText]=useState(''),[runner,setRunner]=useState('proton'),[proton,setProton]=useState('');
  function load(result) {
    setData(result);setValues(result.settings);setChanges({});
    setArgumentsText((result.launch?.arguments || []).join('\n'));
    setRunner(result.launch?.runner || result.runner);setProton(result.launch?.proton_path ?? result.proton_path);
  }
  useEffect(()=>{
    panel.current?.scrollIntoView({block:'start'});
    let current=true;
    action('/api/game-settings',{game_id:game.id,operation:'get'}).then(result=>{if(current)load(result);}).catch(err=>{if(current)setError(err.message);}).finally(()=>{if(current)setBusy(false);});
    return ()=>{current=false;};
  },[game.id]);
  function change(key,value){setValues(old=>({...old,[key]:value}));setChanges(old=>({...old,[key]:value}));setSaved(false);}
  async function run(operation,overrides) {
    setBusy(true);setError('');setSaved(false);
    try {
      const launch={arguments:argumentsText.split('\n').filter(line=>line.trim())};
      if(data?.can_compatibility)Object.assign(launch,{runner,proton_path:proton});
      const result=await action('/api/game-settings',{game_id:game.id,operation,...(operation==='apply'?{values:overrides || changes,launch}:{})});
      if(operation==='hardware')setHardware(result.hardware);else {load(result);setSaved(true);}
    }catch(err){setError(err.message);}finally{setBusy(false);}
  }
  function field(item) {
    const value=values[item.key];
    return <label key={item.key} htmlFor={'game-setting-'+item.key}>{translate(item.label)}
      {item.choices?<select id={'game-setting-'+item.key} disabled={busy} value={value===undefined?'':String(value)} onChange={event=>change(item.key,item.choices.find(option=>String(option)===event.target.value))}>
        {value===undefined && <option value="">—</option>}{value!==undefined && !item.choices.includes(value) && <option value={String(value)} disabled>{valueName(item.key,value)}</option>}{item.choices.map(option=><option key={String(option)} value={String(option)}>{valueName(item.key,option)}</option>)}
      </select>:<input id={'game-setting-'+item.key} type="number" min={item.min} max={item.max} step="1" required disabled={busy} value={value ?? item.min} onChange={event=>change(item.key,Number(event.target.value))}/>}
    </label>;
  }
  return <section ref={panel} className="port-setup-panel game-settings-panel" aria-label="Ustawienia gry">
    <div className="form-section-title"><strong>Ustawienia gry</strong><button type="button" className="icon-button" aria-label="Zamknij formularz" onClick={onClose}><X size={16}/></button></div>
    <p className="form-help">Ustawienia są opcjonalne. Przycisk Graj uruchamia grę bez otwierania tego panelu.</p>
    {error && <p className="game-settings-error" role="alert">{error}</p>}
    {!data && busy && <p role="status"><Spinner/>Wczytywanie ustawień…</p>}
    {data && <form onSubmit={event=>{event.preventDefault();run('apply');}}>
      {data.driver==='pinyon' && <><p className="form-help">Pinyon Shift · ustawienia oryginalnego launchera. Dalsze ustawienia ekranu i sterowania są dostępne w grze pod F6.</p><p className="form-help">FSR 2/3 wymagają bibliotek FidelityFX, a DLSS zgodnego sprzętu i bibliotek. Wybór opcji nie potwierdza jej dostępności.</p></>}
      {data.driver==='pinyon-legacy' && <p className="form-help">Ustawienia korzystają z łatki starszego portu Linux.</p>}
      {data.driver==='fh2' && <p className="form-help">FH2 pozostaje eksperymentalny. Ten silnik udostępnia poniższe opcje; rozgrywka nie jest jeszcze potwierdzona.</p>}
      <div className="game-settings-grid">{data.fields.filter(item=>!item.advanced).map(field)}</div>
      {data.can_hardware && <div className="game-settings-hardware"><button type="button" className="outline" disabled={busy} onClick={()=>run('hardware')}><Cpu size={17}/>Sprawdź sprzęt i zalecenia</button>{hardware && <div role="status"><p translate="no">{hardware.description}</p><p translate="no">{hardware.recommendation?.label} · {hardware.recommendation?.reason}</p>{hardware.recommendation?.warning && <p translate="no">{hardware.recommendation.warning}</p>}<button type="button" className="text-link" disabled={busy || !hardware.recommendation?.preset} onClick={()=>run('apply',{game_preset:hardware.recommendation.preset})}>Zastosuj zalecany profil</button></div>}</div>}
      {data.fields.some(item=>item.advanced) && <details className="game-settings-advanced"><summary>Zaawansowane ustawienia grafiki</summary><div className="game-settings-grid">{data.fields.filter(item=>item.advanced).map(field)}</div><p className="form-help">Limit FPS: 0 oznacza brak limitu.</p></details>}
      <details className="game-settings-advanced"><summary>Opcje uruchamiania</summary>
        {data.can_compatibility && <div className="game-settings-grid"><label>Uruchamianie<select disabled={busy} value={runner} onChange={event=>{setRunner(event.target.value);setSaved(false);}}><option value="proton">Proton</option><option value="wine">Wine</option></select></label>{runner==='proton' && <label>Wersja Protona<select disabled={busy} value={proton} onChange={event=>{setProton(event.target.value);setSaved(false);}}><option value="">Automatycznie — dostępna wersja</option>{proton && !boot.runners?.proton?.some(tool=>tool.path===proton) && <option value={proton}>{proton}</option>}{boot.runners?.proton?.map(tool=><option key={tool.path} value={tool.path}>{tool.name}</option>)}</select></label>}</div>}
        <label htmlFor="game-launch-arguments">Dodatkowe argumenty (jeden w wierszu)<textarea id="game-launch-arguments" disabled={busy} rows="3" value={argumentsText} onChange={event=>{setArgumentsText(event.target.value);setSaved(false);}}/></label>
        <p className="form-help">Używaj argumentów zgodnych z instrukcją podłączonego programu.</p>
      </details>
      {data.config_path && <details className="game-settings-advanced"><summary>Plik konfiguracji</summary><code translate="no">{data.config_path}</code>{data.backup_path && <p><span>Kopia ustawień</span><br/><code translate="no">{data.backup_path}</code></p>}</details>}
      {saved && <p className="port-build-ready" role="status"><Check size={16}/>Zapisano. Ustawienia zostaną użyte przy następnym uruchomieniu.</p>}
      <div className="port-setup-actions"><button type="button" className="outline" onClick={onClose}>Zamknij</button>{data.fields.length>0 && <button type="button" className="outline" disabled={busy} onClick={()=>run('reset')}><ArrowCounterClockwise size={16}/>Domyślne</button>}{data.can_restore && <button type="button" className="outline" disabled={busy} onClick={()=>run('restore')}>Przywróć kopię ustawień</button>}<button type="submit" className="primary" disabled={busy}>{busy?<Spinner/>:<Check size={17}/>}Zapisz</button></div>
    </form>}
  </section>;
}
