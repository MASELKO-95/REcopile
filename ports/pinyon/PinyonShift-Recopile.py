#!/usr/bin/env python3
"""Run Pinyon Shift's original CLI from the downloadable source tools package.

Copyright (C) 2026 MASELKO-95. GPL-3.0-only. Added 2026-10-20.
The embedded Pinyon Shift sources retain their BSD-2-Clause license.
RE:COPILE imports these sources itself and calls their CLI directly.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile


def main():
    package = Path(__file__).resolve().parent
    payload = package / 'pinyon-shift-source.zip'
    manifest = json.loads((package / 'package.json').read_text())
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    if digest != manifest['source_sha256']:
        raise SystemExit('Pinyon Shift source checksum mismatch; download the tools again.')
    root = package / 'source'
    marker = root / '.pinyon-source-sha256'
    if not marker.is_file() or marker.read_text().strip() != digest:
        if root.exists():
            raise SystemExit('Existing source directory was retained. Extract this tools package into a new folder.')
        temporary = Path(tempfile.mkdtemp(prefix='.pinyon-source-', dir=package))
        try:
            with zipfile.ZipFile(payload) as archive:
                for member in archive.infolist():
                    name = member.filename
                    target = temporary / name
                    if '\\' in name or ':' in name or not target.resolve().is_relative_to(temporary.resolve()):
                        raise SystemExit('Unsafe source archive path.')
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member) as source, target.open('xb') as dest:
                            shutil.copyfileobj(source, dest)
            (temporary / '.pinyon-source-sha256').write_text(digest + '\n')
            temporary.rename(root)
        finally:
            if temporary.exists(): shutil.rmtree(temporary)
    os.execv(sys.executable, [sys.executable, str(root / 'tools/pinyon.py'), *sys.argv[1:]])


if __name__ == '__main__': main()
