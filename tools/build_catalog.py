#!/usr/bin/env python3
"""Build an offline, provenance-preserving title catalog from Libretro DATs.

This imports metadata, never game images. Run with --download to refresh the
upstream files; the ordinary build uses already downloaded research files.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INPUTS = [
    ("xbox360", "xbox360-disc.dat", "metadat/redump/Microsoft - Xbox 360.dat", "Redump"),
    ("xbox360", "xbox360-digital.dat", "metadat/no-intro/Microsoft - Xbox 360 (Digital).dat", "No-Intro"),
    ("ps2", "ps2-disc.dat", "metadat/redump/Sony - PlayStation 2.dat", "Redump"),
    ("ps3", "ps3-disc.dat", "metadat/redump/Sony - PlayStation 3.dat", "Redump"),
    ("ps3", "ps3-psn.dat", "dat/Sony - PlayStation 3.dat", "GameTDB / Libretro"),
]
XBOX_ONE_INPUTS = [
    ("xboxone-a-l.html", "https://en.wikipedia.org/wiki/List_of_Xbox_One_games_(A%E2%80%93L)"),
    ("xboxone-m-z.html", "https://en.wikipedia.org/wiki/List_of_Xbox_One_games_(M%E2%80%93Z)"),
]


class XboxOneTable(HTMLParser):
    """Read only the game list table, without loading images or other assets."""
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.cells = []
        self.cell = None
        self.link = ""
        self.rows = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            if self.depth or attrs.get("id") == "softwarelist": self.depth += 1
        if not self.depth: return
        if tag == "tr": self.cells, self.link = [], ""
        if tag == "td": self.cell = []
        if tag == "sup": self.skip += 1
        if tag == "br" and self.cell is not None: self.cell.append(", ")
        if tag == "a" and self.cell is not None and not self.cells and not self.link:
            href = attrs.get("href", "")
            if href.startswith(("https://en.wikipedia.org/wiki/", "./", "/wiki/")) and ":" not in href.rsplit("/", 1)[-1]:
                self.link = href.replace("./", "https://en.wikipedia.org/wiki/", 1) if href.startswith("./") else "https://en.wikipedia.org" + href if href.startswith("/wiki/") else href

    def handle_endtag(self, tag):
        if not self.depth: return
        if tag == "sup": self.skip = max(0, self.skip - 1)
        if tag == "td" and self.cell is not None:
            self.cells.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        if tag == "tr" and len(self.cells) >= 7:
            self.rows.append((self.cells, self.link))
        if tag == "table": self.depth -= 1

    def handle_data(self, data):
        if self.cell is not None and not self.skip: self.cell.append(data)


def key(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).casefold()
    return "".join(c for c in text if c.isalnum())


def title_id(platform: str, title: str) -> str:
    return platform + "-" + hashlib.sha256(key(title).encode()).hexdigest()[:16]


def clean_title(name: str) -> str:
    # Regional/revision tags are metadata. Preserve parentheses in actual titles.
    tag = r"\s+\((?:USA|Europe|Japan|World|Asia|Australia|Korea|China|Russia|Germany|France|Spain|Italy|UK|Canada|Brazil|Scandinavia|Netherlands|Taiwan|Hong Kong|Disc\s|Disk\s|Rev\s|v\d|En(?:,|\))|Fr(?:,|\))|De(?:,|\))|Ja(?:,|\))|XBLA|PSN|Platinum|Classics|Greatest Hits|Game of the Year)[^)]*\)"
    return re.sub(tag, "", name, flags=re.IGNORECASE).strip()


def field(block: str, name: str) -> str:
    match = re.search(r"(?m)^\s*" + name + r'\s+"((?:\\.|[^"\\])*)"', block)
    return match.group(1).replace('\\"', '"').replace("\\\\", "\\") if match else ""


def compile_catalog(input_dir: Path) -> dict:
    games: dict[str, dict] = {}
    provenance = []
    for platform, filename, upstream, attribution in INPUTS:
        raw = (input_dir / filename).read_bytes()
        text = raw.decode("utf-8-sig")
        blocks = re.split(r"(?m)^game\s*\(\s*$", text)[1:]
        count = 0
        excluded = 0
        for block in blocks:
            name = field(block, "name")
            if not name:
                continue
            # Add-ons, title updates and trial/prototype discs are not standalone games.
            if re.search(r"\((?:Addon|DLC|Title Update|Update|Demo|Beta|Proto|Taikenban|Trial|Video|Sample)(?:\s[^)]*)?\)", name, re.I):
                excluded += 1
                continue
            title = clean_title(name)
            ident = title_id(platform, title)
            game = games.setdefault(ident, {"id": ident, "title": title, "platform": platform, "variants": []})
            serial = field(block, "serial")
            sha = re.search(r"\bsha1\s+([A-Fa-f0-9]{40})", block)
            variant = {"name": name, "serial": serial, "region": field(block, "region"), "catalog": filename}
            if sha:
                variant["sha1"] = sha.group(1).lower()
            if variant not in game["variants"]:
                game["variants"].append(variant)
                count += 1
        provenance.append({
            "platform": platform, "file": filename, "attribution": attribution,
            "url": "https://github.com/libretro/libretro-database/blob/master/" + quote(upstream),
            "raw_url": "https://raw.githubusercontent.com/libretro/libretro-database/master/" + quote(upstream),
            "upstream_version": field(text.split("game (")[0], "version"),
            "sha256": hashlib.sha256(raw).hexdigest(), "variants": count, "excluded_non_games": excluded,
        })
    for filename, url in XBOX_ONE_INPUTS:
        raw = (input_dir / filename).read_bytes()
        parser = XboxOneTable()
        parser.feed(raw.decode("utf-8"))
        if not parser.rows: raise ValueError("Xbox One game table is missing: " + filename)
        for cells, link in parser.rows:
            title, genre, developer, publisher = cells[:4]
            # The upstream list includes announced/cancelled titles as well.
            dates = " ".join(cells[4:7])
            years = re.findall(r"\b(?:19|20)\d{2}\b", dates)
            ident = title_id("xboxone", title)
            games[ident] = {"id": ident, "title": title, "platform": "xboxone", "kind": "catalog",
                "genre": genre, "developer": developer, "publisher": publisher,
                "year": min(map(int, years)) if years else None,
                "wiki_title": link.rsplit("/wiki/", 1)[-1] if link else title,
                "metadata_url": url, "release_note": dates, "variants": []}
        provenance.append({"platform": "xboxone", "file": filename, "attribution": "Wikipedia contributors / CC BY-SA 4.0",
            "url": url, "sha256": hashlib.sha256(raw).hexdigest(), "titles": len(parser.rows)})
    return {"schema_version": 1, "imported_at": datetime.now(timezone.utc).isoformat(), "sources": provenance,
            "games": sorted(games.values(), key=lambda x: (x["platform"], x["title"].casefold()))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--input", type=Path, default=ROOT / ".local/research")
    parser.add_argument("--output", type=Path, default=ROOT / "data/catalog.json.gz")
    args = parser.parse_args()
    if args.download:
        args.input.mkdir(parents=True, exist_ok=True)
        for _, filename, upstream, _ in INPUTS:
            url = "https://raw.githubusercontent.com/libretro/libretro-database/master/" + quote(upstream)
            with urlopen(Request(url, headers={"User-Agent": "Recopile/0.1"}), timeout=60) as response:
                (args.input / filename).write_bytes(response.read(30_000_000))
        for filename, url in XBOX_ONE_INPUTS:
            with urlopen(Request(url, headers={"User-Agent": "Recopile/0.1"}), timeout=60) as response:
                (args.input / filename).write_bytes(response.read(30_000_000))
    result = compile_catalog(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({"titles": len(result["games"]), "platforms": {p: sum(g["platform"] == p for g in result["games"]) for p in ["xbox360", "xboxone", "ps2", "ps3"]}, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
