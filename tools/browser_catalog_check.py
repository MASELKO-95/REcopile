#!/usr/bin/env python3
"""Exercise on-demand artwork in a running, isolated desktop preview."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from browser_check import CDP


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9227)
    parser.add_argument("--url", default="http://127.0.0.1:4785/")
    parser.add_argument("--state-dir", type=Path, default=Path(".local/catalog-preview"))
    parser.add_argument("--output", type=Path, default=Path(".local/review/catalog"))
    parser.add_argument("--editions", action="store_true", help="Check RE:COPILE Edition setup and the Xbox text guide")
    args = parser.parse_args()
    if args.editions:
        from browser_editions_check import run
        return run(args)
    cdp = CDP(args.port)
    checks = []
    def image_count(): return len(list((args.state_dir / "covers").glob("*.*")))
    def language(value):
        cdp.evaluate("(() => {const e=document.querySelector('.compact-language select');e.value=" + json.dumps(value) + ";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
        cdp.wait("document.documentElement.lang === " + json.dumps(value))
    def xbox():
        cdp.evaluate("document.querySelector('.main-nav button').click()")
        cdp.evaluate("[...document.querySelectorAll('.platform-nav button')].find(b=>b.textContent.includes('Xbox One')).click()")
        cdp.wait("document.querySelectorAll('.game-card').length===12 && [...document.querySelectorAll('.game-platform span')].every(e=>e.textContent==='Xbox One')")

    before = image_count()
    cdp.call("Page.navigate", {"url": args.url})
    cdp.wait("document.querySelectorAll('.game-card').length===12")
    if cdp.evaluate("Boolean(document.querySelector('.welcome-content'))"):
        cdp.evaluate("document.querySelector('dialog input[type=checkbox]').click()")
        cdp.evaluate("document.querySelector('dialog .modal-actions button.primary').click()")
        cdp.wait("!document.querySelector('dialog[open]')")
    language("pl")
    xbox()
    time.sleep(3)
    assert image_count() == before, "Browsing downloaded artwork without a search or button click"
    checks.append("Xbox One browsing loads no new artwork")
    cdp.capture(args.output / "xboxone-browse.png")

    # A known title from the first catalog page lets us test manual downloads
    # without triggering search's automatic artwork request first.
    title = cdp.evaluate("[...document.querySelectorAll('.game-title')].map(e=>e.textContent).find(t=>['10 Second Ninja X','101 Ways to Die','11-11: Memories Retold'].includes(t))")
    assert title, cdp.evaluate("[...document.querySelectorAll('.game-title')].map(e=>e.textContent)")
    cdp.click(title)
    cdp.wait("document.querySelector('dialog .game-description dl')")
    cdp.wait("document.querySelector('dialog .game-description a')", timeout=45)
    assert image_count() == before, "Opening a description downloaded artwork"
    assert not cdp.evaluate("[...document.querySelectorAll('dialog .detail-actions button')].some(b=>b.textContent.includes('Skonfiguruj emulator'))")
    checks.append("Xbox One description works without artwork and does not suggest an unassigned emulator")
    cdp.capture(args.output / "description-without-cover.png")
    already_cached = cdp.evaluate("document.querySelector('dialog .detail-art img')?.naturalWidth > 0")
    cdp.evaluate("document.querySelector('dialog .game-description button').click()")
    cdp.wait("document.querySelector('dialog .detail-art img')?.naturalWidth > 0", timeout=45)
    assert image_count() == before + (0 if already_cached else 1), "Manual download did not stay limited to the selected game"
    checks.append("Manual cover download fetches only the selected game")
    cdp.capture(args.output / "manual-cover.png")
    cdp.evaluate("document.querySelector('dialog .modal-head .icon-button').click()")

    cdp.click("Na tym PC")
    cdp.wait("document.querySelector('.page-heading h1')?.textContent === 'Na tym PC'")
    # Xbox One has no shipped packages, so the host view must be empty here.
    cdp.wait("document.querySelector('.empty')")
    checks.append("Host view excludes catalog entries with no declared package")
    cdp.evaluate("document.querySelector('.platform-select select').value='all';document.querySelector('.platform-select select').dispatchEvent(new Event('change',{bubbles:true}))")
    cdp.wait("document.querySelector('.device-options')")
    cdp.capture(args.output / "on-this-pc.png")
    for code, label in [("en", "Download covers"), ("hu", "Borítók letöltése"), ("pl", "Pobierz okładki")]:
        language(code)
        cdp.wait("document.querySelector('.cover-controls button')?.textContent === " + json.dumps(label))
        cdp.capture(args.output / ("device-" + code + ".png"))
    checks.append("Polish, English and Hungarian controls")

    xbox()
    cdp.input(".search-field input", "Forza Horizon 3")
    cdp.wait("document.querySelectorAll('.game-card').length===1 && document.querySelector('.game-title').textContent==='Forza Horizon 3'")
    cdp.wait("document.querySelector('.game-card .cover img')?.naturalWidth > 0", timeout=45)
    cdp.click("Forza Horizon 3")
    cdp.wait("document.querySelector('dialog .game-description p')?.textContent.includes('2016 racing game')")
    cdp.capture(args.output / "xboxone-search.png")
    checks.append("Search automatically caches artwork and description for its visible result")
    cached = image_count()
    cdp.evaluate("document.querySelector('dialog .modal-head .icon-button').click()")
    cdp.evaluate("document.querySelector('.search-field .icon-button').click()")
    cdp.wait("document.querySelectorAll('.game-card').length===12")
    cdp.click("Następne")
    cdp.wait("document.querySelector('.pagination span').textContent.startsWith('13')")
    time.sleep(1)
    assert image_count() == cached, "Paging through the catalog downloaded new artwork"
    checks.append("Pagination without search does not download artwork")

    cdp.click("Kolekcje")
    cdp.wait("document.querySelector('.collections-page')")
    cdp.click("Źródła")
    cdp.wait("document.querySelector('.source-card')")
    cdp.click("Workshop")
    cdp.wait("document.querySelector('.workshop-page')")
    checks.append("Collections, sources and workshop navigation")

    xbox()
    cdp.capture(args.output / "xboxone-compact.png", 447, 800)
    compact = cdp.evaluate("({overflow:document.documentElement.scrollWidth>innerWidth,missingImages:[...document.images].filter(i=>!i.naturalWidth).map(i=>i.src)})")
    assert not compact["overflow"] and not compact["missingImages"], compact
    cdp.capture(args.output / "xboxone-desktop.png")
    assert not cdp.errors, cdp.errors
    report = {"checks": checks, "artwork_before": before, "artwork_after": image_count(), "compact": compact, "console_errors": cdp.errors}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "catalog-browser-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
