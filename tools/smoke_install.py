#!/usr/bin/env python3
"""Download actual public runtimes into an isolated verification library.

Never imports game content or launches downloaded programs.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recopile.service import Launcher
from recopile.storage import game_id

parser = argparse.ArgumentParser()
parser.add_argument("--source", choices=["pinyon-linux", "pinyon", "pcsx2", "rpcs3", "skate3"], default="pinyon-linux")
args = parser.parse_args()
app = Launcher(ROOT, ROOT / ".local/smoke-state", automatic=False)
app.save_preferences({"games_dir": str(ROOT / ".local/SmokeLibrary")})
ident = None if args.source in {"pcsx2", "rpcs3"} else game_id("xbox360", "Skate 3" if args.source == "skate3" else "Forza Horizon")
try:
    job = app.install(args.source, ident)
    start = time.monotonic()
    last = None
    while time.monotonic() - start < 240:
        current = app.store.get("jobs", job["id"])
        marker = current["message"]
        if marker != last:
            print(marker, flush=True)
            last = marker
        if current["status"] not in {"queued", "running"}:
            print(json.dumps({"status": current["status"], "message": current["message"], "result": current.get("result")}, ensure_ascii=False, indent=2))
            if current["status"] != "completed":
                raise SystemExit(1)
            install = current["result"]["install"]
            assert Path(install["manifest"]).is_file()
            assert Path(install["executable"]).is_file()
            assert (Path(install["game_root"]) / "current").resolve() == Path(install["runtime_dir"])
            assert install["checksum_verified"]
            break
        time.sleep(.25)
    else:
        app.jobs.cancel(job["id"])
        raise SystemExit("Verification exceeded four minutes")
finally:
    app.shutdown()
    app.jobs.pool.shutdown(wait=True)
