"""Public catalog documentation generated from catalog metadata. GPL-3.0-only."""

def render(catalog):
    lines=['# RE:COPILE port and project list','',
        'Generated from `data/registry.json`. This list is updated with catalog changes.',
        'Packages are declared by catalog entries; package availability is separate from tested gameplay.',
        'Read each project\'s original README and license inside the launcher before downloading.','',
        '| Project | GitHub owner | Linux | Windows | Channel / status | Links |',
        '| --- | --- | --- | --- | --- | --- |']
    labels={'pinyon':'Pinyon Shift','pinyon-linux':'Pinyon Shift Linux alternative',
        'fh2-recomp':'Forza Horizon 2 Recompiled (original)', 'fh2-recomp-shreyash':'Forza Horizon 2 Recompiled (fork)',
        'fh2-recomp-maselko':'Forza Horizon 2 Recompiled (research fork)',
        'ratchet3-local':'Ratchet & Clank: Up Your Arsenal (Ratchet & Clank 3)','minecraft-ps3-iso':'Minecraft PS3 own-disc / ISO integration'}
    for source in catalog['sources']:
        if source.get('public_listing') is False: continue
        repo=source.get('repo',''); author=repo.split('/')[0] if repo else 'MASELKO-95 (planned integration)'
        assets=source.get('assets_by_system',{})
        if source.get('development_status')=='planned': status='Planned; no ready port'
        elif source.get('development_status')=='in_progress': status='In development; gameplay unverified'
        elif source.get('channel')=='preview': status='Pre-release; unsupported / archived'
        elif source.get('channel')=='final': status='Final catalog channel; see upstream status'
        elif source.get('kind')=='emulator': status='Emulator; per-game compatibility varies'
        else: status='Catalogued project; check author documentation'
        name=labels.get(source['id'],source['name'].split(' · ')[0])
        if source.get('edition')=='recopile': name+=' · RE:COPILE Edition'
        links=f'[Project](https://github.com/{repo}) · [Releases](https://github.com/{repo}/releases)' if repo else 'No public release'
        if source.get('guide'): links+=f" · [Guide]({source['guide']})"
        systems=[]
        for system in ['linux','windows']:
            systems.append('Declared package' if assets.get(system) else 'Experiment only; no package' if system in source.get('experimental_systems',[]) and source.get('development_status')=='in_progress' else 'No declared package')
        lines.append('| '+' | '.join([name,author,*systems,status,links])+' |')
    if catalog.get('porting_tools'):
        lines += ['', '## Porting tools and emulators', '',
            '| Tool | Platform | Type | Links |', '| --- | --- | --- | --- |']
        for tool in catalog['porting_tools']:
            platform={'xbox360':'Xbox 360','ps2':'PlayStation 2','ps3':'PlayStation 3'}[tool['platform']]
            kind='Porting SDK' if tool['kind']=='sdk' else 'Emulator'
            lines.append(f"| {tool['name']} | {platform} | {kind} | [Project](https://github.com/{tool['repo']}) · [Guide]({tool['guide']}) |")
    lines += ['','“Final” identifies the original default channel in this catalog; it does not',
        'override the upstream release status. Unsupported forks are not automatic update sources.','',
        'Ratchet 3: Linux PAL SCES-52456 intro and title screen only; full gameplay and',
        'Windows are unverified. Minecraft PS3 ISO support is planned. Neither entry',
        'provides commercial game source code, game assets, ISO or BIOS files.','',
        'Forza Horizon 2 Recompiled: the original fabioap-cpu project and the ShreyashDesai',
        'fork target the **Xbox 360** edition. Their reviewed READMEs describe a Windows AMD64',
        'experiment that stalls at the loading screen; gameplay is unverified. Neither repository',
        'has published releases or ready Linux / Windows packages. Linux build presets and',
        'a CI workflow do not establish working gameplay. These sources are not assigned',
        'to the Xbox One edition. The README declares BSD-3-Clause for project source and SDK;',
        'the reviewed license file is `rexglue-sdk/LICENSE`, with no separate root LICENSE.','',
        'MASELKO-95 research fork: created from fabioap-cpu on 2026-10-15, with no',
        'independent fixes or game tests yet. It retains the same limitations. No game',
        'files are available for local gameplay validation. Creating a fork does not',
        'establish working gameplay.','',
        '## Catalog updates','',
        'Game metadata is maintained in `data/registry.json`. Players receive catalog updates',
        'without replacing launcher code or reinstalling the application.',
        'This project list and the author profile list are generated from that catalog.',
        'Updates to game programs come from their authors\' GitHub Releases.','']
    return '\n'.join(lines)

def render_repositories(catalog):
    authors=set()
    for source in [*catalog['sources'], *catalog.get('porting_tools',[])]:
        if source.get('public_listing') is False: continue
        for repo in [source.get('repo',''),source.get('documentation_repo',''),*source.get('repos_by_system',{}).values()]:
            if repo: authors.add(repo.split('/')[0])
    return '# Project authors\n\n'+'\n'.join(f'- [{author}](https://github.com/{author})' for author in sorted(authors,key=str.casefold))+'\n'
