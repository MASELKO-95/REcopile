"""Local research projects are private references, never distributable game data."""
from __future__ import annotations
import hashlib
import json
import os
import shlex
import time
from pathlib import Path
from .network import UserError

def information(store,source):
    binding=store.get('settings','project:'+source['id'],{})
    root=Path(binding['root']) if binding.get('root') else None
    result={'name':source['name'],'repo':source.get('repo',''),'version':'experimental-local' if root else 'w trakcie prac',
            'asset_name':'Projekt lokalny · bez publicznej paczki','asset_size':0,'funding':[], 'release_url':source.get('guide'),
            'release_notes':source.get('note',''), 'local':True}
    for key,filename in [('readme','README.md'),('license','LICENSE')]:
        file=root/filename if root else None
        text=file.read_text(encoding='utf-8',errors='replace') if file and file.is_file() and file.stat().st_size<=256000 else ''
        if key=='readme' and not text: text=source.get('note','')+'\n\nGotowego portu i instrukcji instalacji jeszcze nie opublikowano.'
        result[key]={'name':filename,'text':text,'available':bool(text),'url':source.get('guide'),
                     'sha256':hashlib.sha256(text.encode()).hexdigest() if text else '', 'error':'Autor nie dołączył licencji do lokalnego projektu.'}
    result['fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result

def bind_ratchet(launcher,root,game_id):
    if launcher.system_key() != 'linux':
        raise UserError('Ten lokalny eksperyment Ratcheta wymaga Linuxa. Windows nie został potwierdzony.')
    if not isinstance(root,str) or not root.strip() or len(root)>4096:
        raise UserError('Wskaż folder lokalnego projektu Ratcheta.')
    root=Path(root).expanduser().resolve()
    script=root/'tools/run-native.sh'
    binary=root/'build/native/ps2xRuntime/ratchet-recomp'
    if not (root/'README.md').is_file() or not script.is_file() or not binary.is_file():
        raise UserError('Nie znaleziono lokalnego README, skryptu startowego i programu Ratcheta.')
    launcher.store.put('settings','project:ratchet3-local',{'root':str(root),'connected_at':time.time(),'read_only':True})
    directory=launcher.store.root/'local-launchers'
    directory.mkdir(exist_ok=True)
    wrapper=directory/'ratchet3.sh'
    wrapper.write_text('#!/bin/sh\nexec /bin/bash '+shlex.quote(str(script))+'\n',encoding='utf-8')
    wrapper.chmod(0o755)
    game=launcher.require_game(game_id)
    old=launcher.store.get('installs',game_id) or {'id':game_id,**launcher.game_location(game_id,game['title'],game['platform']),'play_seconds':0}
    install={**old,'source_id':'ratchet3-local','version':'experimental-local','local_executable':str(wrapper),
             'experimental':True,'ready':False,'installed_at':time.time(),'supported_systems':['linux'],
             'local_system':'linux','runner':'native','edition':'recopile'}
    launcher.save_install(game_id,install)
    launcher.add_library(game_id)
    return install
