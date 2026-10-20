import React from 'react';

export function LanguageSelect({value,onChange,compact=false,disabled=false}) {
  return <label className={'language-control '+(compact?'compact-language':'')}>
    {!compact && <span>Język interfejsu</span>}
    <select aria-label="Język interfejsu" value={value} disabled={disabled} onChange={event=>onChange(event.target.value)}>
      {[['en','English'],['pl','Polski'],['hu','Magyar']].map(([key,name])=><option translate="no" key={key} value={key}>{compact?key.toUpperCase():name}</option>)}
    </select>
  </label>;
}
