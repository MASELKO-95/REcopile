from __future__ import annotations
import hashlib
import json
import platform
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode
from .network import UserError, validate_repo
from .platforms import device_options

STATUSES = {"great":"Działa świetnie", "playable":"Grywalna", "limited":"Z ograniczeniami", "broken":"Nie działa", "unknown":"Brak raportów"}

def device_info():
    system = "Android" if __import__('os').environ.get("RECOPILE_ANDROID") else platform.system()
    gpu = ""
    try:
        if system == "Linux" and shutil.which("nvidia-smi"):
            result = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, timeout=3)
            if not result.returncode: gpu = result.stdout.strip()[:200]
        if not gpu and system == "Linux" and shutil.which("lspci"):
            result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=3)
            line = next((line for line in result.stdout.splitlines() if any(label in line for label in ["VGA compatible controller", "3D controller", "Display controller"])), "")
            gpu = line.partition(": ")[2][:200]
        if system == "Windows":
            result = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"], capture_output=True, text=True, timeout=5)
            gpu = result.stdout.strip()[:200]
    except (OSError, subprocess.TimeoutExpired): pass
    value = {"system": system, "architecture": platform.machine(), "os_version": platform.release(), "gpu": gpu or "Nie ustalono", "cpu": platform.processor() or platform.machine()}
    if system == "Android":
        try:
            from java import jclass
            info = json.loads(jclass("com.recopile.launcher.PlatformBridge").deviceInfo())
            value.update(info)
        except Exception: pass
    value["fingerprint"] = hashlib.sha256((value["system"] + "|" + value["architecture"] + "|" + value["gpu"] + "|" + value.get("model", "")).casefold().encode()).hexdigest()[:24]
    return value

def validate_reports(value):
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("reports"), list) or len(value["reports"]) > 50000:
        raise UserError("Niepoprawna baza zgodności.")
    for report in value["reports"]:
        if report.get("status") not in STATUSES or report.get("status") == "unknown" or not isinstance(report.get("game_id"), str) or len(report["game_id"]) > 100:
            raise UserError("Niepoprawny raport zgodności.")
        if report.get("system") not in {"Linux", "Windows", "Android"}:
            raise UserError("Niepoprawny system w raporcie.")
        if len(report.get("notes", "")) > 3000 or not isinstance(report.get("approved", False), bool):
            raise UserError("Niepoprawne szczegóły raportu.")
    return value

class Compatibility:
    def __init__(self, store):
        self.store = store
        self.device = device_info()

    def public_reports(self):
        cached = self.store.get("settings", "public_compatibility")
        return (cached or json.loads((self.store.app_root / "data/compatibility.json").read_text()))["reports"]

    def describe(self, game):
        reports = [r for r in self.public_reports() if r.get("approved") and r["game_id"] == game["id"] and r["system"] == self.device["system"]]
        same = [r for r in reports if r.get("device_fingerprint") == self.device["fingerprint"]]
        latest = max(same, key=lambda r:r.get("reported_at", 0)) if same else None
        system_key = {"Linux":"linux", "Windows":"windows", "Android":"android"}.get(self.device["system"], "")
        options = device_options(game, system_key)
        if game["kind"] == "catalog": support = "Brak integracji uruchamiania w katalogu"
        elif game["kind"] == "emulation": support = "Przez zewnętrzny emulator" if system_key == "android" else "Przez emulator"
        elif options and all(o.get('manual') for o in options): support = "Ręczne pobranie od autora" if system_key == 'windows' else "Windows przez Proton / Wine · działanie niepotwierdzone"
        elif any(o["via"] == "native" for o in options): support = "Paczka lub lokalny program dla " + self.device["system"]
        elif options: support = "Windows przez Proton / Wine · działanie niepotwierdzone"
        else: support = "Brak paczki dla " + self.device["system"]
        return {"status": latest["status"] if latest else "unknown", "label": STATUSES[latest["status"]] if latest else "Brak raportu tego urządzenia",
                "matching_reports": len(same), "system_reports": len(reports), "support": support, "reports": reports[-30:], "device": self.device}

    def submit_local(self, game, data, preferences):
        status = data.get("status")
        if status not in STATUSES or status == "unknown": raise UserError("Wybierz ocenę działania.")
        notes = str(data.get("notes", "")).strip()
        if not notes or len(notes) > 3000: raise UserError("Opisz krótko działanie gry (do 3000 znaków).")
        fps = data.get("fps")
        if fps not in (None, ""):
            try: fps = float(fps)
            except (ValueError, TypeError): raise UserError("Podaj liczbę FPS.")
            if not 0 <= fps <= 1000: raise UserError("Niepoprawna liczba FPS.")
        report = {"id": uuid.uuid4().hex, "game_id": game["id"], "title": game["title"], "platform": game["platform"],
            "system": self.device["system"], "architecture": self.device["architecture"], "gpu": self.device["gpu"], "cpu": self.device["cpu"], "model": self.device.get("model", ""),
            "device_fingerprint": self.device["fingerprint"], "status": status, "fps": fps or None, "notes": notes,
            "port_version": str(data.get("port_version", ""))[:100], "source_id": str(data.get("source_id", ""))[:100], "reported_at": time.time(), "approved": False}
        self.store.put("compatibility_reports", report["id"], report)
        repo = preferences.get("launcher_repo", "")
        issue_url = None
        if repo:
            repo = validate_repo(repo)
            body = "Raport działania gry na moim urządzeniu.\n\n```recopile-compatibility\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n\nRaport wymaga sprawdzenia przez opiekuna katalogu."
            issue_url = "https://github.com/" + repo + "/issues/new?" + urlencode({"title": "[Zgodność] " + game["title"] + " / " + self.device["system"], "body": body, "labels": "compatibility-report"})
        return {"report": report, "issue_url": issue_url, "message": "Raport zapisany lokalnie. Publiczna ocena pojawi się po zatwierdzeniu zgłoszenia w GitHubie."}
