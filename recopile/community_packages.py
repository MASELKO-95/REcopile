"""Resolve a listed project's unambiguous release through the normal installer.

Copyright (C) 2026 MASELKO-95. GPL-3.0-only. Added 2026-10-30.
"""
import re
from pathlib import Path

from .network import UserError, fetch_json, validate_repo, validate_url

EXCLUDED = re.compile(r'source|symbols|debug|pdb|server|updater|translation|(?:^|[-_.])arm(?:64|32|hf|v[5-8]\w*)|aarch\d+|macos|darwin|android', re.I)


class NoCompatiblePackage(UserError):
    """No package matched; different from an ambiguous or invalid release."""


def resolve(source, system):
    if system not in {'linux', 'windows'}:
        raise UserError('Dla tego systemu nie ma jeszcze obsługi paczek z list.')
    repo = validate_repo(source['repo'])
    releases = fetch_json('https://api.github.com/repos/' + repo + '/releases?per_page=30')
    if not isinstance(releases, list):
        raise UserError('Nie udało się odczytać wydań projektu.')
    for release in releases:
        if release.get('draft'):
            continue
        candidates = []
        for asset in release.get('assets', []):
            name = asset.get('name', '')
            if not name or Path(name).name != name or '\\' in name or EXCLUDED.search(name):
                continue
            archive = name.lower().endswith(('.zip', '.tar.gz', '.tar.xz', '.tgz', '.7z'))
            native = name.endswith('.AppImage')
            installer = name.lower().endswith('.exe')
            if system == 'linux' and (native or archive and re.search(r'linux|lin64|steam.?deck|\bdeck\b', name, re.I)):
                candidates.append(asset)
            elif system == 'windows' and (installer or archive and re.search(r'windows|win64|win[-_](?:x64|amd64|x86_64)', name, re.I)):
                candidates.append(asset)
        appimages = [a for a in candidates if a['name'].endswith('.AppImage')]
        if system == 'linux' and appimages:
            candidates = appimages
        if len(candidates) > 1:
            raise UserError('Wydanie ma kilka paczek dla tego systemu. Wybierz paczkę w edycji źródła.')
        if len(candidates) != 1:
            continue
        asset = candidates[0]
        validate_url(asset.get('browser_download_url', ''))
        installer = asset['name'].lower().endswith('.exe')
        candidate = {**source, 'asset_pattern': asset['name'].replace('[', '[[]'),
            'assets_by_system': {**source.get('assets_by_system', {}), system: asset['name'].replace('[', '[[]')},
            'executable': asset['name'] if installer else '',
            'executables_by_system': {**source.get('executables_by_system', {}), system: asset['name'] if installer else ''},
            'adapter': 'installer' if installer else 'native', 'trusted': True,
            'resolved_system': system,
            'auto_executable': True, 'package_resolved': True,
            'scan_releases': True, 'allow_prerelease': True, 'auto_update': False}
        candidate.pop('origin', None)
        candidate.pop('development_status', None)
        return candidate
    raise NoCompatiblePackage('Autor nie opublikował rozpoznanej paczki dla tego systemu. Sprawdź instrukcję lub podłącz własną kompilację.')


def find_entrypoint(root, system):
    candidates = []
    utilities = {'python', 'python3', 'ffmpeg', 'ffplay', '7z', '7za', 'extract-xiso', 'rexglue', 'cmake', 'ninja'}
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            continue
        relative_parts = {part.casefold() for part in path.relative_to(root).parts[:-1]}
        helper = re.search(r'crash(?:pad|report|handler|dumper)|^unins\d*$|(?:^|[-_.])(?:uninstall|updater|redist|vcredist|tests?)(?:$|[-_.])', path.stem, re.I)
        if path.stem.lower() in utilities or helper or relative_parts.intersection({'tests', '__tests__', 'unit-tests'}):
            continue
        if system == 'windows' and path.suffix.lower() == '.exe':
            candidates.append(path)
        elif system == 'linux' and not re.search(r'\.so(?:\.|$)', path.name):
            with path.open('rb') as stream:
                if stream.read(4) == b'\x7fELF': candidates.append(path)
    launchers = [p for p in candidates if 'launcher' in p.stem.lower()]
    if len(launchers) == 1:
        candidates = launchers
    if len(candidates) != 1:
        raise UserError('Nie znaleziono jednoznacznego pliku startowego. Uzupełnij nazwę w źródle lub dodaj własną kompilację.')
    return candidates[0]
