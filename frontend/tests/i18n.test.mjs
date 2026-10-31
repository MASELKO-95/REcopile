import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

// Run the actual translator with Vite's raw TSV imports materialized for Node.
const root=new URL('../src/i18n/',import.meta.url);
let source=await readFile(new URL('index.js',root),'utf8');
const imports=[...source.matchAll(/import (\w+) from '(\.\/[^']+)\?raw';/g)];
for(const [statement,name,path] of imports){
  const raw=await readFile(new URL(path,root),'utf8');
  source=source.replace(statement,`const ${name}=${JSON.stringify(raw)};`);
  for(const line of raw.trim().split('\n'))assert.equal(line.split('\t').length,3,`Invalid translation row: ${line}`);
}
const {configure,translate,translateProps}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

test('English downloads and engine strings do not fall back to Polish',()=>{
  configure('en');
  assert.equal(translate('Sprawdzanie aktualizacji'),'Checking for updates');
  assert.equal(translate('Instalacje i aktualizacje, w jednym miejscu.'),'Installations and updates, all in one place.');
  assert.equal(translate('Xenia / własny adapter'),'Xenia / custom adapter');
  assert.equal(translate('Sprawdzanie: Example Port'),'Checking: Example Port');
  assert.equal(translateProps('p',{children:'Sprawdzanie listy: Example'}).children,'Checking list: Example');
});
test('Hungarian and Polish still follow the selected language',()=>{
  configure('hu');assert.equal(translate('Sprawdzanie aktualizacji'),'Frissítések keresése');
  configure('pl');assert.equal(translate('Sprawdzanie aktualizacji'),'Sprawdzanie aktualizacji');
});
