import short from './short.tsv?raw';
import messages from './messages.tsv?raw';
import toolMessages from './tools.tsv?raw';
const dictionary=new Map();
for(const line of (short+'\n'+messages+'\n'+toolMessages).split('\n')) { const parts=line.split('\t'); if(parts.length===3) dictionary.set(parts[0],parts.slice(1)); }
let language='pl';
try { language=localStorage.getItem('recopile-language') || 'pl'; } catch {}
const patterns=[...dictionary].filter(([key])=>/\{\d+\}/.test(key)).map(([key,values])=>{
  const indices=[];
  const escaped=key.split(/(\{\d+\})/).map(part=>{if(/^\{\d+\}$/.test(part)){indices.push(Number(part.slice(1,-1)));return '(.+?)';}return part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');}).join('');
  return {expression:new RegExp('^'+escaped+'$'),indices,values};
});
export const locales={pl:'pl-PL',en:'en-GB',hu:'hu-HU'};
export function currentLanguage(){return language;}
export function configure(value){language=Object.hasOwn(locales,value)?value:'pl';if(typeof document!=='undefined')document.documentElement.lang=language;try{localStorage.setItem('recopile-language',language);}catch{}}
export function translate(value){
  if(language==='pl'||typeof value!=='string')return value;
  const key=value.trim(),index=language==='hu'?1:0;
  let output=dictionary.get(key)?.[index];
  if(!output)for(const pattern of patterns){const match=key.match(pattern.expression);if(match){output=pattern.values[index].replace(/\{(\d+)\}/g,(_,n)=>match[pattern.indices.indexOf(Number(n))+1]||'');break;}}
  if(!output)return value;
  return value.match(/^\s*/)[0]+output+value.match(/\s*$/)[0];
}
export function translateProps(type,props){
  if(!props||type==='pre'||props.translate==='no')return props;
  if(typeof type!=='string' && type!==Symbol.for('react.fragment'))return props;
  const copy={...props};
  for(const key of ['aria-label','placeholder','title','alt'])if(typeof copy[key]==='string')copy[key]=translate(copy[key]);
  if(typeof copy.children==='string')copy.children=translate(copy.children);
  else if(Array.isArray(copy.children))copy.children=copy.children.map(child=>typeof child==='string'?translate(child):child);
  return copy;
}
