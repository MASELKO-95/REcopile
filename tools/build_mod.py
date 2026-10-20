#!/usr/bin/env python3
"""Build a .recopilemod package and two desktop installer shortcuts."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from recopile.mods import validate_manifest
from recopile.network import UserError,safe_member
parser=argparse.ArgumentParser(); parser.add_argument('folder',type=Path); parser.add_argument('--output',type=Path,default=ROOT/'artifacts/mods')
args=parser.parse_args(); folder=args.folder.resolve(); value=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
if not (folder/'README.md').is_file() or not (folder/'LICENSE').is_file(): raise SystemExit('Wymagane README.md i LICENSE.')
if 'Uzupełnij rzeczywistą licencję' in (folder/'LICENSE').read_text(encoding='utf-8'): raise SystemExit('Najpierw wybierz licencję własnego moda.')
files=[]
for path in sorted((folder/'payload').rglob('*')):
    if path.is_symlink(): raise SystemExit('Dowiązania są niedozwolone.')
    if path.is_file() and path.name!='.keep':
        rel=path.relative_to(folder).as_posix(); target=path.relative_to(folder/'payload').as_posix()
        files.append({'source':rel,'target':target,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
value['files']=files; validate_manifest(value)
args.output.mkdir(parents=True,exist_ok=True); name=value['id']+'-'+value['version']; package=args.output/(name+'.recopilemod')
if package.exists(): raise SystemExit('Ta paczka już istnieje. Zwiększ wersję.')
with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
    z.writestr('manifest.json',json.dumps(value,ensure_ascii=False,indent=2))
    for filename in ['README.md','LICENSE',*[f['source'] for f in files]]: z.write(folder/filename,filename)
(args.output/(name+'-install.cmd')).write_text('@echo off\nstart "" "%~dp0'+package.name+'"\n',encoding='utf-8')
shell=args.output/(name+'-install.sh'); shell.write_text('#!/bin/sh\nexec xdg-open "$(dirname "$0")/'+package.name+'"\n',encoding='utf-8'); shell.chmod(0o755)
digest=hashlib.sha256(package.read_bytes()).hexdigest(); (args.output/(package.name+'.sha256')).write_text(digest+'  '+package.name+'\n')
print('Paczka gotowa:',package); print('Instalatory otwierają ją w zainstalowanym Recopile; nie wykonują skryptów z moda.')
