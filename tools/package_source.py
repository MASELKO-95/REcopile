#!/usr/bin/env python3
"""Package only explicit source/build inputs, never the surrounding workspace.

GPL-3.0-only. Copyright (C) 2026 MASELKO-95. Added 2026-10-19.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from recopile import __version__

def build():
    paths=set()
    for name in ('launcher.py','start.sh','requirements.txt','requirements-build.txt','README.md','LICENSE','NOTICE',
                 'PRIVACY.md','THIRD_PARTY_NOTICES.md','PORTS.md','REPOSITORIES.md','ROADMAP.md','CHANGELOG.md','.gitignore'):
        paths.add(ROOT/name)
    for folder,patterns in {
        'recopile':['*.py'],'tools':['*.py'],'tests':['*.py'],'docs':['*.md'],
        'data':['*.json','*.json.gz'],'frontend/src':['*.jsx','*.js','*.css','*.tsv'],
        'frontend/scripts':['*.mjs'],'frontend/worker':['*.js'],'frontend/tests':['*.mjs'],
        'frontend/public/assets/fonts':['*.ttf','*-LICENSE.txt'],
    }.items():
        for pattern in patterns: paths.update((ROOT/folder).rglob(pattern))
    paths.update(p for p in (ROOT/'ports/pinyon').rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and p.suffix != '.pyc')
    for relative in ('frontend/package.json','frontend/package-lock.json','frontend/index.html','frontend/vite.config.mjs',
                     'frontend/.openai/hosting.json','frontend/public/favicon.svg','desktop/package.json',
                     'desktop/package-lock.json','desktop/main.cjs','desktop/preload.cjs','desktop/updater.cjs','desktop/build/icon.png'):
        paths.add(ROOT/relative)
    missing=[str(p.relative_to(ROOT)) for p in paths if not p.is_file()]
    if missing: raise RuntimeError('Missing source/build inputs: '+', '.join(sorted(missing)))
    out=ROOT/'artifacts/desktop';out.mkdir(parents=True,exist_ok=True)
    target=out/f'Recopile-{__version__}-source.zip'
    manifest={}
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT): raise RuntimeError('External source input: '+str(path))
            relative=path.relative_to(ROOT).as_posix()
            raw=path.read_bytes()
            manifest[relative]=hashlib.sha256(raw).hexdigest()
            archive.write(path,'recopile-'+__version__+'/'+relative)
        archive.writestr('recopile-'+__version__+'/SOURCE-MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'source':str(target),'files':len(manifest),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},indent=2))
    return target

if __name__=='__main__':build()
