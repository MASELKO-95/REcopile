from __future__ import annotations
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from recopile.network import Cancelled, UserError
from recopile.port_setup import build_state, setup_command, stream_tool
from recopile.service import Launcher
from recopile.storage import game_id
from recopile.storage import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = '''import json, pathlib, sys
root=pathlib.Path(__file__).resolve().parents[1]
args=sys.argv[1:]
print('::pinyon::'+json.dumps({'stage':'verify','percent':100,'message':'Verified fixture'}),flush=True)
if 'setup' in args and '--verify-only' not in args:
    folder=root/'.local/game/base';folder.mkdir(parents=True,exist_ok=True)
    (folder/'default.xex').write_text('test-owned-data')
    (root/'.local/setup-state.json').write_text(json.dumps({'result':'ready'}))
    marker=(root/'.pinyon-source-sha256').read_text().strip()
    (root/'.local/build.json').write_text(json.dumps({'pinyon_shift_source_payload_sha256':marker}))
    executable=root/'out/build/linux-amd64-release/pinyon_shift'
    executable.parent.mkdir(parents=True,exist_ok=True);executable.write_text('#!/bin/sh\\nexit 0\\n');executable.chmod(0o755)
    print('::pinyon::'+json.dumps({'stage':'play','percent':100,'message':'Fixture build complete'}),flush=True)
'''


class PortSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="recopile-port-test-")
        self.root = Path(self.tmp.name)
        self.app = Launcher(ROOT, self.root / "state", automatic=False)
        self.ident = game_id("xbox360", "Forza Horizon")
        self.app.save_preferences({"games_dir": str(self.root / "library")})
        paths = self.app.game_location(self.ident, "Forza Horizon", "xbox360")
        self.runtime = Path(paths["game_root"]) / "versions/fixture"
        self.runtime.mkdir(parents=True)
        self.payload = self.runtime / "pinyon-shift-source.zip"
        self.write_payload()
        self.install = {**paths, "id": self.ident, "source_id": "pinyon", "version": "v-test", "runtime_dir": str(self.runtime), "executable": str(self.runtime / "PinyonShiftLauncher"), "ready": False, "adapter": "pinyon"}
        self.app.save_install(self.ident, self.install)
        self.input = self.root / "my copy ; $(unchanged).iso"
        self.input.write_bytes(b"owned fixture, not a game image")

    def tearDown(self):
        self.app.shutdown()
        self.app.jobs.pool.shutdown(wait=True)
        self.app.media.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def write_payload(self, script=FIXTURE, extra=None):
        files = {"tools/pinyon.py": script, "tools/pinyon_setup.py": "", "tools/setup-preview.ps1": "", "config/supported-dumps.json": "{}", "CMakeLists.txt": "", "README.md": "Fixture readme", "LICENSE": "Fixture license"}
        files.update(extra or {})
        with zipfile.ZipFile(self.payload, "w") as archive:
            for name, text in files.items(): archive.writestr(name, text)

    def wait_job(self, job):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.app.store.get("jobs", job["id"])
            if result["status"] not in {"queued", "running"}: return result
            time.sleep(.01)
        self.fail("Port preparation timed out")

    def prepare(self, **changes):
        return self.app.port_setup.prepare(self.ident, {"path": str(self.input), "owned": True, **changes})

    def test_verification_does_not_mark_downloaded_tools_as_a_built_game(self):
        self.assertFalse(self.app.detail(self.ident)["port_setup"]["ready"])
        result = self.wait_job(self.prepare(verify_only=True))
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["result"]["verified"])
        self.assertFalse(result["result"]["ready"])
        self.assertFalse(self.app.store.get("installs", self.ident)["ready"])
        self.assertEqual(self.input.read_bytes(), b"owned fixture, not a game image")

    def test_build_uses_upstream_cli_and_preserves_the_existing_save(self):
        engine = self.app.port_setup.ensure_source(self.install)
        save = engine / ".local/preview/user/ForzaProfile/ForzaProfile"
        save.parent.mkdir(parents=True)
        save.write_bytes(b"existing save")
        result = self.wait_job(self.prepare())
        self.assertEqual(result["status"], "completed", result)
        install = self.app.store.get("installs", self.ident)
        self.assertEqual(install["pinyon_state_root"], str(engine / ".local/preview"))
        self.assertEqual(save.read_bytes(), b"existing save")
        self.assertTrue(self.app.detail(self.ident)["port_setup"]["ready"])
        command, cwd = self.app.port_setup.launch_command(install)
        self.assertEqual(Path(command[1]), engine / "tools/pinyon.py")
        self.assertIn("launch", command)
        self.assertIn(str(engine / ".local/preview"), command)
        self.assertNotIn("PinyonShiftLauncher", " ".join(command))
        self.assertEqual(cwd, engine)

    def test_success_exit_without_a_matching_build_record_is_not_ready(self):
        self.write_payload(script="print('verify finished')\n")
        result = self.wait_job(self.prepare())
        self.assertEqual(result["status"], "failed")
        self.assertFalse(self.app.detail(self.ident)["port_setup"]["ready"])

    def test_official_setup_does_not_change_an_existing_alternative_source_state(self):
        self.app.save_install(self.ident,{**self.install,'source_id':'pinyon-linux','ready':True})
        game=self.app.detail(self.ident)
        self.assertTrue(game['install']['ready'])
        self.assertEqual(game['install']['source_id'],'pinyon-linux')
        self.assertFalse(game['port_setup']['installed'])

    def test_pinyon_keeps_its_name_and_removes_old_branding_without_rewriting_custom_urls(self):
        source=self.app.source('pinyon')
        self.assertEqual(source['name'],'Pinyon Shift')
        self.assertNotEqual(source.get('edition'),'recopile')
        self.app.store.put('sources','pinyon',{**source,'edition':'recopile','name':'Pinyon Shift · RE:COPILE Edition','repo':'example/player-chosen-repo','user_override':True})
        migrated=Store(ROOT,self.root/'state').get('sources','pinyon')
        self.assertEqual(migrated['name'],'Pinyon Shift')
        self.assertNotEqual(migrated.get('edition'),'recopile')
        self.assertEqual(migrated['repo'],'example/player-chosen-repo')
        self.assertTrue(migrated['user_override'])
        self.assertTrue(self.app.port_setup.supports(migrated))

    def test_changed_payload_keeps_old_source_and_private_game_files(self):
        engine = self.app.port_setup.ensure_source(self.install)
        private = engine / ".local/game/base/kept.dat"
        private.parent.mkdir(parents=True)
        private.write_bytes(b"private owned files")
        self.write_payload(extra={"tools/new-version.py": "print('updated')"})
        updated = self.app.port_setup.ensure_source(self.install)
        self.assertNotEqual(updated, engine)
        self.assertEqual(private.read_bytes(), b"private owned files")
        self.assertTrue((engine / "tools/pinyon.py").exists())

    def test_source_payload_cannot_supply_game_data_or_escape_its_folder(self):
        for bad_name in ("../escape", ".local/game/base/default.xex", "generated/guest.cpp"):
            with self.subTest(name=bad_name):
                self.write_payload(extra={bad_name: "not installed"})
                with self.assertRaises(UserError): self.app.port_setup.ensure_source(self.install)
        self.assertFalse((self.root / "escape").exists())

    def test_ownership_is_required_and_input_is_passed_as_one_argument(self):
        with self.assertRaises(UserError): self.prepare(owned=False)
        with self.assertRaises(UserError): self.prepare(path="")
        engine = self.app.port_setup.ensure_source(self.install)
        command = setup_command(engine, self.input, "linux", verify_only=True)
        self.assertEqual(command[command.index("--iso") + 1], str(self.input))
        with patch("recopile.port_setup.powershell_command", return_value="powershell.exe"):
            command = setup_command(engine, self.input, "windows", verify_only=True)
        self.assertIn("-JsonEvents", command)
        self.assertIn("-VerifyOnly", command)
        self.assertEqual(command[command.index("-IsoPath") + 1], str(self.input))

    def test_folder_verification_stops_before_upstream_build_fallthrough(self):
        # Current upstream setup --verify-only --extracted falls through to
        # provisioning/build. Its verified-folder importer is a separate API.
        module = '''from pathlib import Path
def Progress(value): return value
def verify_folder(path, progress):
    assert path.is_dir() and progress is True
    (Path(__file__).resolve().parents[1]/'verified-folder').write_text(str(path))
'''
        self.write_payload(script="raise RuntimeError('The setup CLI must not build in verify-only mode')", extra={"tools/pinyon_setup.py": module})
        folder = self.root / "own extracted ; game"
        folder.mkdir()
        marker = folder / "default.xex"
        marker.write_bytes(b"owned fixture")
        result = self.wait_job(self.prepare(path=str(folder), verify_only=True))
        self.assertEqual(result["status"], "completed", result)
        install = self.app.store.get("installs", self.ident)
        self.assertEqual((Path(install["engine_root"])/"verified-folder").read_text(), str(folder))
        self.assertEqual(marker.read_bytes(), b"owned fixture")
        self.assertFalse(self.app.detail(self.ident)["port_setup"]["ready"])

    def test_cancellation_stops_a_silent_process(self):
        stop = threading.Event()
        timer = threading.Timer(.3, stop.set)
        timer.start()
        started = time.monotonic()
        try:
            with self.assertRaises(Cancelled):
                stream_tool([sys.executable, "-c", "import time; time.sleep(30)"], self.root, self.root / "cancel.log", lambda **_: None, stop.is_set)
        finally: timer.cancel()
        self.assertLess(time.monotonic() - started, 4)
