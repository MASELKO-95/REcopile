"""Catalog platforms are separate from the operating system running a port."""

PLATFORMS = {"xbox360", "xboxone", "ps2", "ps3", "other"}


def device_options(game, system):
    options = []
    install = game.get("install") or {}
    if install.get('adapter') == 'steam' and not install.get('local_executable') and system in {'linux', 'windows'}:
        # Steam chooses the actual native/Proton launch configuration. Scanning
        # a manifest does not establish a platform or gameplay compatibility.
        options.append({'system': system, 'via': 'steam', 'local': True})
    local_system = install.get("local_system")
    if install.get("local_executable") and local_system:
        if local_system == system or system == "linux" and local_system == "windows":
            options.append({"system": local_system, "via": "proton" if local_system != system else "native", "local": True})
    for source in game.get("sources", []):
        if source.get("origin") == "development" or source.get("kind") == "emulator":
            continue
        if source.get('origin') == 'external':
            for target in (["linux", "windows"] if system == "linux" else [system]):
                if target in source.get('manual_systems', []):
                    options.append({'system': target, 'via': 'proton' if target != system else 'native',
                                    'source_id': source['id'], 'manual': True})
            continue
        patterns = source.get("assets_by_system", {"linux": source.get("asset_pattern")})
        for target in (["linux", "windows"] if system == "linux" else [system]):
            if patterns.get(target):
                options.append({"system": target, "via": "proton" if target != system else "native", "source_id": source["id"]})
    return options
