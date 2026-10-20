#!/usr/bin/env python3
"""Start the portable Recopile launcher and its loopback-only local service."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def open_window(url, state_root):
    for browser in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        program = shutil.which(browser)
        if program:
            subprocess.Popen([program, "--app=" + url, "--user-data-dir=" + str(state_root / "browser"),
                              "--class=Recopile", "--no-first-run", "--disable-component-update", "--window-size=1440,960"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Recopile Games Hub — lokalny launcher gier")
    parser.add_argument("--port", type=int, default=4783)
    parser.add_argument("--data-dir", type=Path, default=APP_ROOT / ".local/state")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--no-auto-updates", action="store_true")
    parser.add_argument("--ignore-update", action="store_true")
    args = parser.parse_args()
    state_root = args.data_dir.expanduser().resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    marker = state_root / "pending-launcher.json"
    if marker.is_file() and not args.ignore_update and not getattr(sys, "frozen", False):
        try:
            info = json.loads(marker.read_text())
            target = Path(info["root"]).resolve()
            if target.is_relative_to((state_root / "launcher-updates").resolve()) and target != APP_ROOT and (target / "launcher.py").is_file():
                command = [sys.executable, str(target / "launcher.py"), "--data-dir", str(state_root), "--port", str(args.port)]
                if args.no_window:
                    command.append("--no-window")
                if args.no_auto_updates:
                    command.append("--no-auto-updates")
                # The selected version keeps serving the same state and installs.
                os.execv(sys.executable, command)
        except (ValueError, KeyError, OSError):
            print("Nie można użyć przygotowanej aktualizacji; uruchamiam bieżącą wersję.", file=sys.stderr)
    from recopile.network import UserError
    from recopile.server import create_server
    from recopile.service import Launcher
    try:
        import fcntl
        lock = (state_root / "launcher.lock").open("w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Ta biblioteka jest już otwarta w innym procesie launchera.")
            if not args.no_window:
                open_window(f"http://127.0.0.1:{args.port}/", state_root)
            return 0
    except ImportError:
        lock = None
    launcher = Launcher(APP_ROOT, state_root, automatic=not args.no_auto_updates, scan_steam=True)
    try:
        server = create_server(launcher, args.port)
    except (UserError, OSError) as exc:
        launcher.shutdown()
        print(str(exc), file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{server.server_port}/"
    print("Recopile jest uruchomiony: " + url, flush=True)
    print("Biblioteka: " + str(state_root), flush=True)
    if not args.no_window:
        threading.Timer(0.5, open_window, args=(url, state_root)).start()
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        launcher.shutdown()
        server.server_close()
        if lock:
            lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
