#!/usr/bin/env python3
"""Run Proton's built-in cmd test in an isolated prefix; never run a game."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from recopile import runners

def main():
    root=ROOT/'.local/runner-smoke';root.mkdir(parents=True,exist_ok=True)
    tools=runners.discover()
    if not tools['proton']:raise SystemExit('No installed Proton found.')
    install={'local_executable':'cmd.exe','local_system':'windows','user_root':str(root),'runner':'proton'}
    argv,env=runners.command(install,{},dict(os.environ),'linux',tools)
    env.update({'SteamGameId':'0','SteamAppId':'0','PROTON_LOG':'1'})
    with (root/'smoke.log').open('w') as log:
        result=subprocess.run([*argv,'/c','echo RecopileRunnerOK'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    text=(root/'smoke.log').read_text(errors='replace')
    report={'proton':tools['proton'][0]['name'],'runtime':bool(tools['steam_runtime']),
        'exit_code':result.returncode,'marker_found':'RecopileRunnerOK' in text,
        'prefix_inside_workspace':(root/'compat').resolve().is_relative_to(ROOT),
        'gameplay_tested':False,'log':str(root/'smoke.log')}
    (root/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    if result.returncode or not report['marker_found']:raise SystemExit(1)

if __name__=='__main__':main()
