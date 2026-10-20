"""Steam-style library folders without touching Steam's own manifests."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


def folder_name(title: str, platform: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip(" .")[:120] or "Gra"
    label = {"xbox360": "Xbox 360", "xboxone": "Xbox One", "ps2": "PS2", "ps3": "PS3", "other": "PC", "engine": "Silnik"}.get(platform, platform)
    return clean + " (" + label + ")"


def location(library: Path, ident: str, title: str, platform: str):
    library = library.expanduser().resolve()
    apps = library / "recopileapps"
    return {"library_root": str(library),
            "game_root": str(apps / ("engines" if ident.startswith("engine-") else "common") / folder_name(title, platform)),
            "user_root": str(library / "userdata/local" / ident),
            "download_root": str(apps / "downloading" / ident),
            "manifest": str(apps / ("appmanifest_" + ident + ".json"))}


def write_manifest(install: dict):
    path = install.get("manifest")
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"schema_version": 1, **install}, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(target)


def point_current(install: dict):
    runtime = install.get("runtime_dir")
    if not runtime:
        return
    if os.name == "nt":
        # Windows symlinks can require privileges. The manifest is authoritative.
        pointer = Path(install["game_root"]) / "current.json"
        temp = pointer.with_suffix(".tmp")
        temp.write_text(json.dumps({"runtime_dir":runtime, "version":install.get("version")}), encoding="utf-8")
        temp.replace(pointer)
        return
    current = Path(install["game_root"]) / "current"
    temporary = current.with_name(".current.tmp")
    if current.exists() and not current.is_symlink():
        # Leave a manually created file/directory untouched.
        return
    if temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(Path(runtime).relative_to(current.parent), target_is_directory=True)
    temporary.replace(current)
