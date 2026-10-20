#!/usr/bin/env python3
"""Small Chromium DevTools client for local UI checks; no browser framework."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


class CDP:
    def __init__(self, port):
        with urlopen(f"http://127.0.0.1:{port}/json/list") as response:
            target = next(t for t in json.load(response) if t["type"] == "page")
        url = urlparse(target["webSocketDebuggerUrl"])
        self.socket = socket.create_connection((url.hostname, url.port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall((f"GET {url.path} HTTP/1.1\r\nHost: {url.hostname}:{url.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += self.socket.recv(1)
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if not header.startswith(b"HTTP/1.1 101 ") or expected not in header:
            raise RuntimeError(header.decode())
        self.ident = 0
        self.errors = []
        self.started_at = time.time() * 1000
        self.call("Runtime.enable")
        self.call("Page.enable")
        self.call("Log.enable")

    def read(self, size):
        data = b""
        while len(data) < size:
            block = self.socket.recv(size - len(data))
            if not block:
                raise RuntimeError("DevTools connection closed")
            data += block
        return data

    def receive(self):
        chunks = []
        while True:
            first, second = self.read(2)
            size = second & 127
            if size == 126:
                size = struct.unpack("!H", self.read(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self.read(8))[0]
            mask = self.read(4) if second & 128 else None
            payload = self.read(size)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if first & 15 == 8:
                raise RuntimeError("DevTools closed")
            if first & 15 == 9:
                self.send_frame(payload, opcode=10)
                continue
            chunks.append(payload)
            if first & 128:
                return json.loads(b"".join(chunks))

    def send_frame(self, payload, opcode=1):
        size = len(payload)
        prefix = bytes([128 | opcode, 128 | size]) if size < 126 else bytes([128 | opcode, 128 | 126]) + struct.pack("!H", size) if size < 65536 else bytes([128 | opcode, 128 | 127]) + struct.pack("!Q", size)
        mask = os.urandom(4)
        self.socket.sendall(prefix + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def call(self, method, params=None):
        self.ident += 1
        ident = self.ident
        self.send_frame(json.dumps({"id": ident, "method": method, "params": params or {}}).encode())
        while True:
            value = self.receive()
            if value.get("method") == "Runtime.exceptionThrown":
                self.errors.append(value["params"])
            elif value.get("method") == "Log.entryAdded" and value["params"]["entry"]["level"] == "error" and value["params"]["entry"].get("timestamp", 0) >= self.started_at:
                self.errors.append(value["params"])
            if value.get("id") == ident:
                if "error" in value:
                    raise RuntimeError(value["error"])
                return value.get("result", {})

    def evaluate(self, code):
        result = self.call("Runtime.evaluate", {"expression": code, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def wait(self, condition, timeout=15):
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self.evaluate("Boolean(" + condition + ")"):
                return
            time.sleep(0.1)
        raise RuntimeError("UI wait failed: " + condition)

    def click(self, text):
        label = json.dumps(text)
        result = self.evaluate(f"(() => {{ const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==={label}); if(!b) return false; b.click(); return true; }})()")
        if not result:
            raise RuntimeError("Button not found: " + text)

    def input(self, selector, text):
        self.evaluate(f"(() => {{ const e=document.querySelector({json.dumps(selector)}); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,{json.dumps(text)}); e.dispatchEvent(new Event('input',{{bubbles:true}})); }})()")

    def capture(self, path, width=1440, height=1000):
        self.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
        self.evaluate("document.fonts.ready.then(()=>true)")
        time.sleep(0.3)
        self.wait("[...document.images].every(i=>i.complete)")
        screenshot = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(screenshot["data"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9225)
    parser.add_argument("--url", default="http://127.0.0.1:4783/")
    parser.add_argument("--test-url", default="http://127.0.0.1:4784/")
    parser.add_argument("--output", type=Path, default=Path(".local/review"))
    parser.add_argument("--capture-only", action="store_true")
    args = parser.parse_args()
    cdp = CDP(args.port)
    checks = []
    def onboarding():
        cdp.wait("document.querySelector('.game-card') || document.querySelector('.startup p')")
        if cdp.evaluate("Boolean(document.querySelector('.welcome-content'))"):
            cdp.capture(args.output / "first-launch.png")
            if cdp.evaluate("document.querySelector('dialog').textContent.includes('Wspieranie autora reklamami')"):
                raise RuntimeError("Android ad preference leaked into desktop")
            cdp.click('Licencja Recopile')
            cdp.wait("document.querySelector('.document-text').textContent.includes('GNU GENERAL PUBLIC LICENSE')")
            cdp.click('Prywatność')
            cdp.wait("document.querySelector('.document-text').textContent.includes('Recopile nie ma formularza hasła')")
            cdp.evaluate("document.querySelector('dialog input[type=checkbox]').click()")
            cdp.click('Przejdź do biblioteki')
            cdp.wait("!document.querySelector('dialog[open]')")
            checks.append('First launch license/privacy and no desktop ads')
    if not args.capture_only:
        cdp.call("Page.navigate", {"url": args.test_url})
        cdp.wait("document.querySelectorAll('.game-card').length === 12")
        onboarding()
        cdp.input('input[aria-label="Szukaj gry w katalogu"]', 'Forza Horizon')
        cdp.wait("document.querySelectorAll('.game-card').length > 0 && [...document.querySelectorAll('.game-title')].every(e=>e.textContent.toLowerCase().includes('forza horizon'))")
        checks.append("Catalog search")
        cdp.evaluate("document.querySelector('[aria-label=\"Wyczyść wyszukiwanie\"]').click()")
        cdp.wait("document.querySelectorAll('.game-card').length === 12")
        cdp.evaluate("document.querySelector('[role=switch][aria-label=\"Tylko rekompilacje\"]').click()")
        cdp.wait("document.querySelectorAll('.game-card').length === 5")
        if not cdp.evaluate("[...document.querySelectorAll('.cover-badge')].every(e=>e.textContent.startsWith('Rekompilacja'))"):
            raise RuntimeError("Emulation leaked into recompilation-only view")
        cdp.call("Page.reload")
        cdp.wait("document.querySelectorAll('.game-card').length === 5")
        checks.append("Recompilation-only filter and persistence")
        cdp.evaluate("document.querySelector('[role=switch][aria-label=\"Tylko rekompilacje\"]').click()")
        cdp.wait("document.querySelectorAll('.game-card').length === 12")
        cdp.click('Forza Horizon')
        cdp.wait("document.querySelector('dialog[open] #game-source')")
        if cdp.evaluate("document.querySelectorAll('#game-source option').length") != 2:
            raise RuntimeError("Forza source picker missing an upstream")
        cdp.capture(args.output / "forza-detail.png")
        cdp.evaluate("document.querySelector('dialog [aria-label=\"Zamknij\"]').click()")
        checks.append("Game detail and source selection")
        cdp.evaluate("document.querySelector('[aria-label=\"Otwórz profil\"]').click()")
        cdp.wait("document.querySelector('.profile-metrics')")
        cdp.click('Generuj podsumowanie')
        cdp.wait("document.querySelector('.profile-export img')")
        cdp.capture(args.output / 'profile-summary.png')
        checks.append('Local profile and real PNG export')
        cdp.click('Biblioteka')
        cdp.click('Zainstalowane')
        cdp.wait("document.querySelector('.empty')")
        checks.append("Installed empty state")
        cdp.click('Ustawienia')
        cdp.wait("document.querySelector('.storage-library')")
        cdp.capture(args.output / "storage-settings.png")
        checks.append("Steam-style storage manager")
        for button, selector in [('Emulatory', '.engine-card'), ('Źródła', '.source-card'), ('Narzędzia', '.tools-page'), ('Pobieranie', '.page-toolbar')]:
            cdp.click(button)
            cdp.wait("document.querySelector(" + json.dumps(selector) + ")")
            checks.append(button + " navigation")
        cdp.click('Dodaj grę lub źródło')
        cdp.wait("document.querySelector('dialog .add-form')")
        cdp.click('Gra spoza launchera')
        cdp.wait("document.querySelector('input[placeholder=\"/home/gracz/Gry/moja-gra\"]')")
        cdp.capture(args.output / "add-game.png")
        cdp.evaluate("document.querySelector('dialog [aria-label=\"Zamknij\"]').click()")
        checks.append("Add game dialog and local/GitHub modes")
    cdp.call("Page.navigate", {"url": args.url})
    cdp.wait("document.querySelectorAll('.game-card').length === 12")
    onboarding()
    cdp.capture(args.output / "launcher-desktop.png")
    desktop = cdp.evaluate("({width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,missingImages:[...document.images].filter(i=>!i.naturalWidth).map(i=>i.src),cards:document.querySelectorAll('.game-card').length})")
    cdp.capture(args.output / "launcher-reference-size.png", 1440, 1440)
    cdp.capture(args.output / "launcher-compact.png", 447, 800)
    compact = cdp.evaluate("({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,missingImages:[...document.images].filter(i=>!i.naturalWidth).map(i=>i.src)})")
    cdp.capture(args.output / "launcher-desktop.png")
    if desktop["overflow"] or compact["overflow"] or desktop["missingImages"] or compact["missingImages"]:
        raise RuntimeError({"desktop": desktop, "compact": compact})
    report = {"checks": checks, "desktop": desktop, "compact": compact, "console_errors": cdp.errors}
    (args.output / "browser-check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, ensure_ascii=False))
    if cdp.errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
