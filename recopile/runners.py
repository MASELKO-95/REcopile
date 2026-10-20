"""Use installed Proton/UMU/Wine without shell commands or Steam account access."""
from __future__ import annotations
import os
import re
import shutil
from pathlib import Path
from .network import UserError
from .steam import discover_libraries

def discover(preferences=None):
    preferences=preferences or {}
    found,clients=discover_libraries(preferences.get('steam_libraries',[]))
    libraries=[Path(item['path']) for item in found if item['available']]
    tools=[]
    seen=set()
    for base in dict.fromkeys(libraries):
        for directory in [base/'compatibilitytools.d',base/'steamapps/common']:
            if not directory.is_dir(): continue
            for item in directory.iterdir():
                script=item/'proton'
                if script.is_file() and str(script.resolve()) not in seen:
                    seen.add(str(script.resolve()))
                    tools.append({'name':item.name,'path':str(script.resolve()),'root':str(item.resolve()),'client':str(clients[0]) if clients else '',
                                  'origin':'Steam' if directory.name=='common' else 'Narzędzie użytkownika'})
    custom=preferences.get('proton_path','')
    if custom:
        p=Path(custom).expanduser().resolve()
        if p.is_dir(): p=p/'proton'
        if p.is_file() and str(p) not in seen: tools.append({'name':p.parent.name,'path':str(p),'root':str(p.parent),'client':str(clients[0]) if clients else '', 'origin':'Wskazany ręcznie'})
    def score(tool):
        match=re.search(r'(?:Proton[ -]?|Proton-)(\d+)',tool['name'],re.I)
        return (tool['origin']=='Steam' and 'Experimental' not in tool['name'] and 'Hotfix' not in tool['name'],int(match[1]) if match else 0,tool['name'])
    tools.sort(key=score,reverse=True)
    runtime=None
    for base in dict.fromkeys(libraries):
        script=base/'steamapps/common/SteamLinuxRuntime_sniper/_v2-entry-point'
        if script.is_file(): runtime=str(script.resolve()); break
    return {'proton':tools,'steam_runtime':runtime,'wine':shutil.which('wine'),'umu':preferences.get('umu_path') or shutil.which('umu-run')}

def executable_system(path):
    with Path(path).open('rb') as stream: header=stream.read(4)
    if header.startswith(b'MZ') or Path(path).suffix.lower()=='.exe': return 'windows'
    if header==b'\x7fELF' or header.startswith(b'#!') or os.name!='nt': return 'linux'
    return 'windows'

def command(install,preferences,env,host,tools=None):
    exe=install['local_executable']
    system=install.get('local_system') or executable_system(exe)
    if system!='windows' or host=='windows':
        if system=='linux' and host=='windows': raise UserError('Ten program jest dla Linuxa. Podłącz wydanie Windows.')
        return [exe],env
    tools=tools or discover(preferences)
    mode=install.get('runner','proton')
    prefix=Path(install['user_root'])/'compat'
    prefix.mkdir(parents=True,exist_ok=True)
    env={**env,'STEAM_COMPAT_DATA_PATH':str(prefix),'WINEPREFIX':str(prefix/'pfx'),'PROTON_LOG_DIR':install['user_root']}
    if mode=='wine':
        if not tools['wine']: raise UserError('Wine nie jest zainstalowane. Wybierz dostępnego Protona lub wskaż program Windows na Windowsie.')
        return [tools['wine'],exe],env
    if mode!='proton': raise UserError('Program Windows na Linuxie wymaga wybrania Protona albo Wine.')
    requested=install.get('proton_path') or preferences.get('proton_path')
    chosen=next((t for t in tools['proton'] if t['path']==requested or t['root']==requested),None) if requested else next(iter(tools['proton']),None)
    if not chosen: raise UserError('Nie znaleziono wybranej wersji Protona. Zainstaluj ją w Steamie lub wskaż plik proton w ustawieniach.')
    if tools.get('umu'):
        env.update({'PROTONPATH':chosen['root'],'GAMEID':'umu-default','STORE':'none'})
        return [tools['umu'],exe],env
    env['STEAM_COMPAT_CLIENT_INSTALL_PATH']=chosen['client']
    argv=[chosen['path'],'waitforexitandrun',exe]
    if tools.get('steam_runtime'): argv=[tools['steam_runtime'],'--verb=waitforexitandrun','--',*argv]
    return argv,env
