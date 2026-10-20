#!/usr/bin/env python3
"""Generate project details and author profile links from the versioned catalog."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0,str(ROOT))
from recopile.catalog_docs import render, render_repositories

def write(root=ROOT):
    catalog=json.loads((root/'data/registry.json').read_text())
    (root/'PORTS.md').write_text(render(catalog),encoding='utf-8')
    (root/'REPOSITORIES.md').write_text(render_repositories(catalog),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    expected=render(json.loads((ROOT/'data/registry.json').read_text()))
    if args.check:
        if not (ROOT/'PORTS.md').is_file() or (ROOT/'PORTS.md').read_text()!=expected:raise SystemExit('PORTS.md needs regeneration.')
        if not (ROOT/'REPOSITORIES.md').is_file() or (ROOT/'REPOSITORIES.md').read_text()!=render_repositories(json.loads((ROOT/'data/registry.json').read_text())): raise SystemExit('REPOSITORIES.md needs regeneration.')
        print('PORTS.md and REPOSITORIES.md match the catalog.')
    else:write();print('Updated PORTS.md.')
