#!/usr/bin/env python3
"""Freeze the local service. Players do not need Python or Node."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bundle = ROOT / '.local/package-input'
bundle.mkdir(parents=True, exist_ok=True)
frontend = bundle / 'frontend/dist/client'
if frontend.exists(): shutil.rmtree(frontend)
shutil.copytree(ROOT / 'frontend/dist/client', frontend)
# Artwork remains a local cache. Do not silently redistribute third-party covers.
covers = frontend / 'assets/covers'
if covers.exists(): shutil.rmtree(covers)
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--name', 'recopile-service',
           '--distpath', str(ROOT / '.local/backend-dist'), '--workpath', str(ROOT / '.local/pyinstaller-work'),
           '--specpath', str(ROOT / '.local'), '--collect-all', 'py7zr', '--collect-all', 'PIL',
           '--exclude-module', 'tkinter', '--exclude-module', 'pytest',
           '--exclude-module', 'recopile.publisher', '--exclude-module', 'owner_publisher']
for source, dest in [(frontend,'frontend/dist/client'),(ROOT/'data','data'),(ROOT/'LICENSE','.'),(ROOT/'NOTICE','.'),(ROOT/'PRIVACY.md','.'),(ROOT/'README.md','.'),(ROOT/'THIRD_PARTY_NOTICES.md','.')]:
    if not source.exists(): raise SystemExit('Missing package input: '+str(source))
    command += ['--add-data',str(source)+':'+dest]
subprocess.run([*command, str(ROOT/'launcher.py')],cwd=ROOT,check=True)
