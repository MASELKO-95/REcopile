import React, { useEffect, useRef, useState } from 'react';
import { ArrowSquareOut, Books, CircleNotch, GameController, X } from '@phosphor-icons/react';
import {currentLanguage,locales} from './i18n/index.js';

export const platforms = { all: 'Wszystkie platformy', xbox360: 'Xbox 360', xboxone: 'Xbox One', ps2: 'PlayStation 2', ps3: 'PlayStation 3', other: 'Inne gry' };
export const modes = { recompile: 'Rekompilacja', emulation: 'Emulacja', native: 'Gra natywna', catalog: 'Brak integracji' };
export const count = n => Number(n || 0).toLocaleString(locales[currentLanguage()]);
export const bytes = n => n >= 1073741824 ? `${(n / 1073741824).toFixed(1)} GB` : n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`;
export const ago = t => t ? new Date(t * 1000).toLocaleString(locales[currentLanguage()], { dateStyle: 'short', timeStyle: 'short' }) : 'Jeszcze nie sprawdzono';
export const activeJob = j => ['queued', 'running'].includes(j.status);
export const Badge = ({ kind, children }) => <span className={`badge ${kind || ''}`}>{children}</span>;
export function TechnologyBadges({game}) {
  return <div className="technology-badges" aria-label="Technologie projektu">{game.declared_technologies?.length ? game.declared_technologies.map(t=><span className="badge muted" key={t.id} translate="no">{t.label}</span>) : <small>Technologie: brak deklaracji</small>}</div>;
}
export const External = ({ href, children, className = '' }) => <a className={className} href={href} target="_blank" rel="noopener noreferrer">{children}<ArrowSquareOut size={14} /></a>;
export const Spinner = () => <CircleNotch className="spin" size={18} />;
export function DeviceBadges({game}) {
  const options=[...new Map((game.device_options || []).map(o=>[o.system+o.via,o])).values()];
  return options.length ? <div className="target-badges device-options">{options.map(o=><Badge key={o.system+o.via} kind={o.via==='proton'?'warning':'muted'}>{o.via==='steam' ? 'Steam · zgodność ustawia klient' : o.via==='proton' ? 'Windows · Proton / Wine · nieprzetestowane' : o.system==='windows' ? 'Windows · na tym PC' : o.system==='linux' ? 'Linux · na tym PC' : 'Android · na tym urządzeniu'}</Badge>)}</div> : null;
}
export function Empty({ icon: Icon = Books, title, text, children }) { return <div className="empty"><Icon size={43} weight="light" /><h2>{title}</h2><p>{text}</p>{children}</div>; }
export function Cover({ game }) { const [missing,setMissing]=useState(false); useEffect(() => setMissing(false),[game.id,game.cover_url]); return <div className="cover">{game.cover_url && !missing ? <img src={game.cover_url} onError={() => setMissing(true)} alt={`Okładka: ${game.title}`} loading="lazy" /> : <div className="no-cover"><GameController size={36} weight="light" /><span>{game.title}</span><small>{game.media_status?.cover === 'missing' ? 'Okładka niedostępna' : game.media_status?.cover === 'error' ? 'Okładka chwilowo niedostępna' : 'Okładka na żądanie'}</small></div>}</div>; }
export function Toggle({ value, onChange, label, small = false }) { return <button type="button" role="switch" aria-checked={value} aria-label={label} className={`switch ${value ? 'on' : ''} ${small ? 'small' : ''}`} onClick={() => onChange(!value)}><span /></button>; }
export function Modal({ title, subtitle, onClose, children, wide = false, dismissible = true }) {
  const ref = useRef(null);
  useEffect(() => { const node = ref.current; node.showModal(); return () => node.close(); }, []);
  return <dialog ref={ref} className={`modal ${wide ? 'wide' : ''}`} onCancel={e => { e.preventDefault(); if (dismissible) onClose(); }} onClick={e => { if (e.target === ref.current && dismissible) onClose(); }}>
    <div className="modal-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{dismissible && <button className="icon-button" aria-label="Zamknij" onClick={onClose}><X size={22} /></button>}</div>{children}
  </dialog>;
}
