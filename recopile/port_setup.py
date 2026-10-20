"""RE:COPILE's setup UI uses the port's reviewed command-line workflow."""
from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path

from .network import Cancelled, UserError, extract, safe_member

STAGES = {"verify": (0, 10), "extract": (10, 20), "tools": (30, 20), "build": (50, 49), "play": (99, 1)}


def python_command(root):
    pinned = sorted((root / ".local/toolchain").glob("python-*/bin/python3"))
    if pinned: return str(pinned[-1])
    if not getattr(sys, "frozen", False): return sys.executable
    command = shutil.which("python3")
    if not command: raise UserError("Przygotowanie tego portu wymaga systemowego Python 3, zgodnie z README autora.")
    return command


def powershell_command():
    for path in (Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe",
                 Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PowerShell/7/pwsh.exe"):
        if path.is_file(): return str(path)
    command = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not command: raise UserError("Przygotowanie tego portu wymaga PowerShell, zgodnie z README autora.")
    return command


def setup_command(root, input_path, system, verify_only=False):
    if system == "windows":
        command = [powershell_command(), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(root / "tools/setup-preview.ps1"), "-ExtractedPath" if input_path.is_dir() else "-IsoPath", str(input_path), "-JsonEvents"]
        if verify_only: command.append("-VerifyOnly")
    elif system == "linux":
        if verify_only and input_path.is_dir():
            # Upstream's --verify-only stops for ISO input, but currently
            # falls through to compilation for --extracted. Call its existing
            # verified-folder importer directly and stop before provisioning.
            code = ("import sys; from pathlib import Path; "
                "sys.path.insert(0, str(Path(sys.argv[1]) / 'tools')); "
                "import pinyon_setup; "
                "pinyon_setup.verify_folder(Path(sys.argv[2]), pinyon_setup.Progress(True))")
            return [python_command(root), "-c", code, str(root), str(input_path)]
        command = [python_command(root), str(root / "tools/pinyon.py"), "setup",
            "--extracted" if input_path.is_dir() else "--iso", str(input_path), "--json"]
        if verify_only: command.append("--verify-only")
    else:
        raise UserError("Ten adapter przygotowania obsługuje Linux i Windows.")
    return command


def build_state(root, system):
    result = {"ready": False, "game_files": (root / ".local/game/base/default.xex").is_file()}
    try:
        state = json.loads((root / ".local/setup-state.json").read_text())
        build = json.loads((root / ".local/build.json").read_text())
        marker = (root / ".pinyon-source-sha256").read_text().strip()
        preset = "win-amd64-release" if system == "windows" else "linux-amd64-release"
        executable = root / "out/build" / preset / ("pinyon_shift.exe" if system == "windows" else "pinyon_shift")
        result["ready"] = bool(result["game_files"] and state.get("result") == "ready" and marker
            and build.get("pinyon_shift_source_payload_sha256") == marker and executable.is_file())
        if result["ready"]: result["built_executable"] = str(executable)
    except (OSError, ValueError): pass
    return result


def stream_tool(command, root, log_path, update, cancelled):
    """Drain output on a reader thread so cancellation works during silent builds."""
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", **flags)
    lines = queue.Queue()
    def read():
        try:
            for line in process.stdout: lines.put(line)
        finally: lines.put(None)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    progress, tail = 0, []
    try:
        with log_path.open("w", encoding="utf-8") as log:
            while True:
                if cancelled(): raise Cancelled("Anulowano przygotowanie portu. Pliki i zapisy pozostają na dysku.")
                try: line = lines.get(timeout=.2)
                except queue.Empty: continue
                if line is None:
                    while process.poll() is None:
                        if cancelled(): raise Cancelled("Anulowano przygotowanie portu. Pliki i zapisy pozostają na dysku.")
                        try: process.wait(timeout=.2)
                        except subprocess.TimeoutExpired: pass
                    break
                log.write(line)
                log.flush()
                tail = (tail + [line.rstrip()])[-12:]
                if line.startswith("::pinyon::"):
                    try:
                        event = json.loads(line[len("::pinyon::"):])
                        if not isinstance(event, dict): continue
                        start, weight = STAGES.get(event.get("stage"), (progress, 0))
                        progress = max(progress, min(99, start + weight * max(0, min(100, float(event.get("percent", 0)))) / 100))
                        update(progress=progress, message=str(event.get("error") or event.get("message") or "Przygotowanie portu")[:500], stage=event.get("stage", ""))
                    except (ValueError, TypeError): pass
        code = process.wait()
        if code:
            raise UserError("Przygotowanie zatrzymane. " + "\n".join(tail)[-1800:])
    finally:
        if process.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            else:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                process.kill()
                process.wait()
        reader.join(timeout=2)
        process.stdout.close()


class PortSetup:
    def __init__(self, launcher): self.launcher = launcher

    def supports(self, source):
        return source.get("id") == "pinyon" and source.get("adapter") == "pinyon"

    def root(self, install):
        if install.get("engine_root"): return Path(install["engine_root"])
        parent = Path(install["game_root"]) / "content/pinyon/source"
        version = str(install.get("version", "local")).removeprefix("v")
        if not version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in version):
            raise UserError("Niepoprawna wersja źródeł portu.")
        return parent / version

    def information(self, game):
        source = next((s for s in game.get("sources", []) if self.supports(s)), None)
        if not source: return None
        install = game.get("install") or {}
        installed = install.get("source_id") == source["id"] and bool(install.get("runtime_dir"))
        result = {"source_id": source["id"], "installed": installed, "ready": False, "game_files": False}
        if installed:
            root = self.root(install)
            result.update(build_state(root, self.launcher.system_key()), engine_root=str(root), input_path=install.get("data_path", ""))
        return result

    def ensure_source(self, install):
        runtime = Path(install["runtime_dir"]).resolve()
        payloads = list(runtime.rglob("pinyon-shift-source.zip"))
        if len(payloads) != 1: raise UserError("W wydaniu portu brakuje jednoznacznej paczki źródeł. Pobierz ponownie narzędzia portu.")
        payload = payloads[0]
        digest = hashlib.sha256(payload.read_bytes()).hexdigest()
        root = self.root(install)
        marker = root / ".pinyon-source-sha256"
        if marker.is_file() and marker.read_text().strip() == digest and (root / "tools/pinyon.py").is_file(): return root
        # A changed payload or an existing user's checkout is retained intact.
        if root.exists() and any(root.iterdir()):
            root = root.with_name(root.name + "-" + digest[:12])
            marker = root / ".pinyon-source-sha256"
            if marker.is_file() and marker.read_text().strip() == digest: return root
            if root.exists() and any(root.iterdir()): raise UserError("Folder tej wersji zawiera inne pliki. Podłącz istniejącą kompilację albo wybierz inną bibliotekę.")
        root.parent.mkdir(parents=True, exist_ok=True)
        stage = root.parent / (".recopile-source-" + uuid.uuid4().hex)
        try:
            with zipfile.ZipFile(payload) as archive:
                for name in archive.namelist():
                    target = safe_member(name, stage)
                    parts = target.relative_to(stage.resolve()).parts
                    if parts and parts[0] in {".local", "out", "generated", ".git"}:
                        raise UserError("Paczka źródeł zawiera lokalne dane, których nie instalujemy.")
            extract(payload, stage, payload.name)
            for filename in ("tools/pinyon.py", "tools/pinyon_setup.py", "tools/setup-preview.ps1", "config/supported-dumps.json", "CMakeLists.txt", "README.md", "LICENSE"):
                if not (stage / filename).is_file(): raise UserError("Paczka źródeł portu jest niekompletna: " + filename)
            (stage / ".pinyon-source-sha256").write_text(digest + "\n", encoding="ascii")
            if root.exists(): root.rmdir()  # Only the empty destination checked above.
            stage.rename(root)
        finally:
            if stage.exists(): shutil.rmtree(stage)
        return root

    def prepare(self, ident, data):
        game = self.launcher.detail(ident)
        info, install = game.get("port_setup"), game.get("install")
        if not info or not info["installed"]: raise UserError("Najpierw pobierz narzędzia portu i przejrzyj README oraz licencję.")
        if data.get("owned") is not True: raise UserError("Potwierdź, że korzystasz z własnej kopii gry.")
        raw_path = data.get("path", "")
        if not isinstance(raw_path, str) or not raw_path.strip() or len(raw_path) > 4096:
            raise UserError("Wskaż ścieżkę do własnego ISO lub folderu gry.")
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not os.access(path, os.R_OK) or not (path.is_dir() or path.suffix.lower() == ".iso"):
            raise UserError("Wskaż czytelny ISO albo wypakowany folder własnej gry.")
        verify_only = data.get("verify_only", False)
        if not isinstance(verify_only, bool): raise UserError("Niepoprawny tryb przygotowania.")
        def work(update, cancelled):
            with self.launcher.process_lock:
                if ident in self.launcher.running: raise UserError("Zamknij grę przed przygotowaniem portu.")
            root = self.ensure_source(install)
            state = Path(install.get("pinyon_state_root") or root / ".local/preview")
            # Reuse a prior standalone launcher's save in place. New installs use
            # the library's userdata; no save is moved, reset, or overwritten.
            legacy_saves = state / "user"
            if not install.get("pinyon_state_root") and (not legacy_saves.is_dir() or not any(p.is_file() for p in legacy_saves.rglob("*"))):
                state = Path(install["user_root"]) / "pinyon"
            current = {**install, "engine_root": str(root), "pinyon_state_root": str(state), "data_path": str(path)}
            current.pop("edition", None)
            self.launcher.save_install(ident, current)
            command = setup_command(root, path, self.launcher.system_key(), verify_only)
            log = self.launcher.store.root / "logs" / ("prepare-" + ident + "-" + str(time.time_ns()) + ".log")
            update(message="Przygotowanie w RE:COPILE · Pinyon Shift", log=str(log), progress=0)
            stream_tool(command, root, log, update, cancelled)
            result = build_state(root, self.launcher.system_key())
            if not verify_only and not result["ready"]:
                raise UserError("Narzędzie zakończyło pracę, ale nie potwierdzono kompletnej kompilacji tej wersji. Sprawdź log przygotowania.")
            if not verify_only:
                self.launcher.save_install(ident, {**current, "ready": True, "setup_completed_at": time.time()})
            return {"verified": True, "ready": result["ready"], "message": "Pliki sprawdzone. Gra nie została zbudowana." if verify_only else "Kompilacja gotowa do uruchomienia. Rozgrywkę ocenia osobny raport zgodności."}
        return self.launcher.jobs.submit("prepare", game["title"] + " · Pinyon Shift", ident, work)

    def launch_command(self, install):
        root = self.root(install)
        if not build_state(root, self.launcher.system_key())["ready"]:
            raise UserError("Przygotuj tę wersję portu w panelu RE:COPILE przed uruchomieniem.")
        state = install.get("pinyon_state_root") or str(Path(install["user_root"]) / "pinyon")
        if self.launcher.system_key() == "windows":
            return [powershell_command(), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "tools/launch-preview.ps1"), "-Configuration", "Release", "-StateRoot", state, "-Json", "-JsonEvents"], root
        return [python_command(root), str(root / "tools/pinyon.py"), "launch", "--state-root", state], root
