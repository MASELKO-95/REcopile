#!/usr/bin/env python3
"""Build player installers and their matching beta updater metadata.

Copyright (C) 2026 MASELKO-95. GPL-3.0-only. Added 2026-10-20.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
subprocess.run(['npm', 'run', 'package', '--', *sys.argv[1:]], cwd=ROOT/'desktop', check=True)
version = json.loads((ROOT/'desktop/package.json').read_text())['version']
if '-beta.' in version:
    for suffix in ('linux.yml', 'mac.yml', 'yml'):
        path = ROOT/'artifacts/desktop'/('latest-'+suffix if suffix != 'yml' else 'latest.yml')
        if path.is_file(): shutil.copy2(path, path.with_name('beta-'+suffix if suffix != 'yml' else 'beta.yml'))
