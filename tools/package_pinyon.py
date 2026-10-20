#!/usr/bin/env python3
"""Build the Pinyon source-tools package from its pinned public checkout.

Copyright (C) 2026 MASELKO-95. GPL-3.0-only. Added 2026-10-20.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PIN = '9331e453e9850d0fcc1c1606dee95db834a9d317'
NAME = 'PinyonShift-0.6.0-Recopile-linux-x86_64.tar.gz'
FORBIDDEN = {'.exe', '.dll', '.obj', '.lib', '.pdb', '.iso', '.xex', '.dxil', '.pnsp',
             '.so', '.apk', '.aab', '.idsig', '.keystore', '.jks', '.dex', '.pyc'}


def build(upstream, output):
    inputs = ROOT / 'ports/pinyon'
    selected = json.loads((inputs / 'payload-inputs.json').read_text())
    # Git archive reads committed inputs only, excluding local game/build state.
    raw = subprocess.check_output(['git', '-C', str(upstream), 'archive', '--format=tar', PIN, '--', *selected])
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            if member.isdir(): continue
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts:
                raise RuntimeError('Unexpected source input: ' + member.name)
            if any(p in {'.local', '.git', '__pycache__', 'generated', 'node_modules'} for p in path.parts):
                raise RuntimeError('Private/generated source input: ' + member.name)
            if path.suffix.lower() in FORBIDDEN:
                raise RuntimeError('Binary source input: ' + member.name)
            files[member.name] = archive.extractfile(member).read()
    changes = {}
    for path in sorted((inputs / 'overrides').rglob('*')):
        if not path.is_file(): continue
        name = path.relative_to(inputs / 'overrides').as_posix()
        files[name] = path.read_bytes()
        changes[name] = hashlib.sha256(files[name]).hexdigest()
    files['SOURCE-CHANGES.md'] = (inputs / 'SOURCE-CHANGES.md').read_bytes()
    provenance = {'schema_version': 1, 'repository': 'https://github.com/arcanite24/pinyon-shift',
                  'commit': PIN, 'dirty': True, 'integration': 'MASELKO-95/recopile', 'modified_files': changes}
    files['config/source-provenance.json'] = (json.dumps(provenance, indent=2) + '\n').encode()
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    manifest = {'schema_version': 1, 'version': '0.6.0-recopile.1', 'kind': 'source-tools',
                'upstream_commit': PIN, 'source_sha256': hashlib.sha256(payload.getvalue()).hexdigest(),
                'game_data_included': False, 'compiled_game_included': False, 'source_changes': changes}
    outer = {'pinyon-shift-source.zip': payload.getvalue(),
             'package.json': (json.dumps(manifest, indent=2) + '\n').encode(),
             'RECOPILE-LICENSE': (ROOT / 'LICENSE').read_bytes()}
    for name in ('PinyonShift-Recopile.py', 'README.md', 'UPSTREAM-LICENSE', 'SOURCE-CHANGES.md'):
        outer[name] = (inputs / name).read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / NAME
    with destination.open('wb') as file, gzip.GzipFile(fileobj=file, mode='wb', mtime=1792454400) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, data in sorted(outer.items()):
                info = tarfile.TarInfo('PinyonShift/' + name)
                info.size = len(data)
                info.mode = 0o755 if name.endswith('.py') else 0o644
                info.mtime = 1792454400
                archive.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_name(NAME + '.sha256').write_text(digest + '  ' + NAME + '\n')
    print(json.dumps({'package': str(destination), 'sha256': digest, 'source_files': len(files)}, indent=2))
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/desktop')
    args = parser.parse_args()
    build(args.upstream.resolve(strict=True), args.output)
