from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from recopile.library import location
from recopile.network import Cancelled, UserError, download, extract, latest_release, safe_member, validate_repo, validate_url
from recopile.server import create_server
from recopile.service import Launcher
from recopile.storage import Store, game_id

ROOT = Path(__file__).resolve().parents[1]


def tar_bytes(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as tar:
        for name, contents in files.items():
            contents = contents.encode() if isinstance(contents, str) else contents
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(contents), 0o755 if name.endswith("run.sh") else 0o644
            tar.addfile(member, io.BytesIO(contents))
    return stream.getvalue()


def release(payload, version="v1.0.0", name="Game-Linux.tar.gz", published="2026-10-01T00:00:00Z"):
    asset = {"name": name, "size": len(payload), "browser_download_url": "https://github.com/example/game/releases/download/" + version + "/" + name,
             "digest": "sha256:" + hashlib.sha256(payload).hexdigest()}
    return {"version": version, "url": "https://github.com/example/game/releases", "asset": asset, "assets": [asset], "published_at": published}


def wait_job(app, job):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        current = app.store.get("jobs", job["id"])
        if current["status"] not in {"queued", "running"}:
            return current
        time.sleep(0.03)
    raise AssertionError("Task timed out")

def fixture_documents(source, metadata):
    fingerprint = hashlib.sha256((source["repo"]+metadata["version"]).encode()).hexdigest()
    return {"repo":source["repo"],"name":source["name"],"version":metadata["version"],"fingerprint":fingerprint,
            "readme":{"available":True,"text":"Test instructions","sha256":"a"*64,"url":"https://github.com/example/game"},
            "license":{"available":True,"text":"Test MIT license","sha256":"b"*64,"url":"https://github.com/example/game"},
            "funding":[],"release_url":metadata["url"],"asset_name":metadata["asset"]["name"],"asset_size":metadata["asset"]["size"]}


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="recopile-test-")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_paths_cannot_escape_install_directory(self):
        for name in ["../evil", "/tmp/evil", "a/../../evil", "..\\evil", "C:/evil", "a\x00b"]:
            with self.subTest(name=name), self.assertRaises(UserError):
                safe_member(name, self.root)

    def test_tar_traversal_is_rejected(self):
        path = self.root / "bad.tar.gz"
        path.write_bytes(tar_bytes({"../escape": "bad"}))
        with self.assertRaises(UserError):
            extract(path, self.root / "out", path.name)
        self.assertFalse((self.root / "escape").exists())

    def test_zip_traversal_is_rejected(self):
        path = self.root / "bad.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("../../escape", "bad")
        with self.assertRaises(UserError):
            extract(path, self.root / "out", path.name)

    def test_tar_symlink_cannot_redirect_later_writes(self):
        path = self.root / "bad.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            link = tarfile.TarInfo("link")
            link.type, link.linkname = tarfile.SYMTYPE, str(self.root)
            tar.addfile(link)
            file = tarfile.TarInfo("link/escape")
            file.size = 3
            tar.addfile(file, io.BytesIO(b"bad"))
        with self.assertRaises(UserError):
            extract(path, self.root / "out", path.name)
        self.assertFalse((self.root / "escape").exists())

    def test_safe_internal_tar_symlink_and_permissions(self):
        path = self.root / "good.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            file = tarfile.TarInfo("bin/run.sh")
            file.size, file.mode = 2, 0o755
            tar.addfile(file, io.BytesIO(b"ok"))
            link = tarfile.TarInfo("run")
            link.type, link.linkname = tarfile.SYMTYPE, "bin/run.sh"
            tar.addfile(link)
        extract(path, self.root / "out", path.name)
        self.assertEqual((self.root / "out/run").read_text(), "ok")
        self.assertTrue((self.root / "out/bin/run.sh").stat().st_mode & 0o100)

    def test_checksum_mismatch_is_rejected_and_partial_removed(self):
        payload = b"a genuine release"
        asset = release(payload)["asset"]
        with patch("recopile.network.open_url", return_value=io.BytesIO(payload)):
            with self.assertRaises(UserError):
                download(asset, self.root / "part", lambda *_: None, lambda: False, "0" * 64)
        self.assertFalse((self.root / "part").exists())

    def test_download_cancellation_keeps_no_partial(self):
        payload = b"data"
        with patch("recopile.network.open_url", return_value=io.BytesIO(payload)):
            with self.assertRaises(Cancelled):
                download(release(payload)["asset"], self.root / "part", lambda *_: None, lambda: True)
        self.assertFalse((self.root / "part").exists())

    def test_only_github_https_sources(self):
        self.assertEqual(validate_repo("https://github.com/owner/game.git"), "owner/game")
        for value in ["http://github.com/owner/repo", "owner/repo/../../thing", "github.com/owner/repo", "owner/$(id)"]:
            with self.assertRaises(UserError):
                validate_repo(value)
        for url in ["http://github.com/file", "https://github.com.evil.example/file", "https://localhost/file", "https://github.com:8080/file", "https://x:y@github.com/file"]:
            with self.assertRaises(UserError):
                validate_url(url)

    def test_source_archive_is_not_selected_as_binary(self):
        metadata = {"tag_name": "v1", "html_url": "https://github.com/owner/game/releases", "assets": [
            {"name": "Game-Linux-source.tar.gz", "browser_download_url": "https://github.com/a"},
            {"name": "Game-Linux-1.tar.gz", "browser_download_url": "https://github.com/b"}]}
        with patch("recopile.network.fetch_json", return_value=metadata):
            value = latest_release({"repo": "owner/game", "asset_pattern": "Game-Linux-*.tar.gz", "exclude_pattern": "*source*"})
        self.assertEqual(value["asset"]["name"], "Game-Linux-1.tar.gz")


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="recopile-test-")
        self.root = Path(self.tmp.name)
        self.app = Launcher(ROOT, self.root / "state", automatic=False)
        self.app.save_preferences({"games_dir": str(self.root / "Library A")})
        self.documents_patch = patch.object(self.app.documents, "get", side_effect=fixture_documents)
        self.documents_patch.start()

    def tearDown(self):
        self.app.shutdown()
        self.app.jobs.pool.shutdown(wait=True)
        self.documents_patch.stop()
        self.tmp.cleanup()

    def add_fixture(self):
        result = self.app.add_source({"repo": "example/game", "name": "Fixture", "title": "Fixture Game", "platform": "other", "kind": "native", "asset_pattern": "Game-Linux.tar.gz", "executable": "run.sh", "trusted": True})
        return result["source"]["id"], result["game"]["id"]

    def reviewed_install(self, sid, ident):
        review = self.app.install(sid, ident)
        if review.get("review_required"):
            return self.app.install(sid, ident, review=review["documents"]["fingerprint"], allow_auto=True,
                license_accepted=True, license_hash=review['documents']['license']['sha256'])
        return review

    def test_offline_catalog_search_and_recompile_provenance(self):
        self.assertGreater(self.app.store.stats()["total"], 15000)
        self.assertEqual(self.app.store.query(q="Forza Horizon", platform="xbox360")["games"][0]["kind"], "recompile")
        self.assertTrue(self.app.store.query(q="SCUS-97399", platform="ps2")["games"])
        self.assertEqual(self.app.store.query(q="Sonic Unleashed", platform="ps3")["games"][0]["kind"], "emulation")
        self.assertEqual(self.app.store.query(mode="recompile")["total"], 5)

    def test_settings_and_custom_source_survive_restart(self):
        ident = game_id("xbox360", "Halo 3")
        self.app.add_source({"repo": "example/game", "name": "My project", "title": "Halo 3", "platform": "xbox360", "kind": "recompile", "asset_pattern": "*Linux*.zip", "executable": "run", "trusted": True, "game_id": ident})
        self.app.save_preferences({"only_recompiled": True, "profile_name": "Test"})
        other = Store(ROOT, self.root / "state")
        self.assertTrue(other.get("settings", "preferences")["only_recompiled"])
        self.assertEqual(other.game(ident)["kind"], "recompile")
        self.assertEqual(len(other.game(ident)["source_ids"]), 1)

    def test_import_layout_and_multiple_library_folders(self):
        ident = game_id("ps2", "God of War")
        image = self.root / "my disc.iso"
        image.write_bytes(b"owned fixture")
        game = self.app.import_game(ident, {"path": str(image), "owned": True})
        install = game["install"]
        self.assertEqual(Path(install["game_root"]).parent, self.root / "Library A/recopileapps/common")
        self.assertTrue(Path(install["manifest"]).is_file())
        self.assertEqual((Path(install["game_root"]) / "gamefiles/input").resolve(), image)
        self.assertFalse(game["install"]["ready"], "A ROM without an engine is not ready to play")
        self.app.save_preferences({"games_dir": str(self.root / "Library B")})
        self.assertEqual(self.app.store.get("installs", ident)["library_root"], str(self.root / "Library A"))
        self.assertEqual(len(self.app.libraries()), 3)  # shipped default + both added folders

    def test_ps3_requires_prepared_folder(self):
        ident = game_id("ps3", "Demon's Souls")
        image = self.root / "my.iso"
        image.write_bytes(b"not a prepared PS3 dump")
        with self.assertRaises(UserError):
            self.app.import_game(ident, {"path": str(image), "owned": True})
        boot = self.root / "PS3/PS3_GAME/USRDIR/EBOOT.BIN"
        boot.parent.mkdir(parents=True)
        boot.write_bytes(b"fixture")
        self.app.import_game(ident, {"path": str(self.root / "PS3"), "owned": True})

    def test_install_update_and_rollback_preserve_user_data(self):
        sid, ident = self.add_fixture()
        payload = tar_bytes({"Game/run.sh": "#!/bin/sh\nexit 0\n", "Game/version.txt": "one"})
        with patch("recopile.service.latest_release", return_value=release(payload)), patch("recopile.network.open_url", side_effect=lambda *_args, **_kwargs: io.BytesIO(payload)):
            result = wait_job(self.app, self.reviewed_install(sid, ident))
        self.assertEqual(result["status"], "completed", result.get("message"))
        first = self.app.store.get("installs", ident)
        self.assertFalse(first["ready"])
        save = Path(first["user_root"]) / "save.dat"
        save.write_text("keep me")
        content = Path(first["game_root"]) / "content"
        content.mkdir()
        (content / "own-game.dat").write_text("own assets")
        payload2 = tar_bytes({"Game/run.sh": "#!/bin/sh\nexit 0\n", "Game/version.txt": "two"})
        source = self.app.source(sid)
        self.app.store.put("sources", sid, {**source, "checked_at": 0})
        with patch("recopile.service.latest_release", return_value=release(payload2, "v1.1.0", published="2026-10-02T00:00:00Z")), patch("recopile.network.open_url", side_effect=lambda *_a, **_k: io.BytesIO(payload2)):
            result = wait_job(self.app, self.reviewed_install(sid, ident))
        self.assertEqual(result["status"], "completed", result.get("message"))
        current = self.app.store.get("installs", ident)
        self.assertEqual(current["version"], "v1.1.0")
        self.assertEqual(save.read_text(), "keep me")
        self.assertEqual((content / "own-game.dat").read_text(), "own assets")
        self.assertTrue(Path(first["runtime_dir"]).is_dir())
        self.assertEqual((Path(current["game_root"]) / "current").resolve(), Path(current["runtime_dir"]))
        self.app.rollback(ident)
        restored = json.loads(Path(current["manifest"]).read_text())
        self.assertEqual(restored["version"], "v1.0.0")
        self.assertEqual(save.read_text(), "keep me")

    def test_failed_install_never_replaces_current_version(self):
        sid, ident = self.add_fixture()
        payload = tar_bytes({"Game/run.sh": "#!/bin/sh\nexit 0\n"})
        metadata = release(payload)
        metadata["asset"]["digest"] = "sha256:" + "0" * 64
        with patch("recopile.service.latest_release", return_value=metadata), patch("recopile.network.open_url", return_value=io.BytesIO(payload)):
            result = wait_job(self.app, self.reviewed_install(sid, ident))
        self.assertEqual(result["status"], "failed")
        self.assertIn("SHA-256", result["message"])
        self.assertIsNone(self.app.store.get("installs", ident))

    def test_download_requires_upstream_documentation_review(self):
        sid, ident = self.add_fixture()
        with patch("recopile.service.latest_release", return_value=release(b"fixture")), patch("recopile.service.download") as downloader:
            result = self.app.install(sid, ident)
        self.assertTrue(result["review_required"])
        downloader.assert_not_called()
        self.assertFalse(self.app.jobs.list())

    def test_auto_updates_wait_for_notice_and_changed_license(self):
        from recopile.legal import ProjectDocuments
        docs = fixture_documents({"repo":"example/game","name":"Test"}, release(b"x"))
        legal = ProjectDocuments(self.app.store)
        legal.accept(docs, docs["fingerprint"], auto=True, license_accepted=True, license_hash=docs['license']['sha256'])
        new = {**docs, "version":"v2", "fingerprint":"c"*64}
        self.assertFalse(legal.permitted(new, automatic=True))
        legal.seen(new["fingerprint"])
        self.assertTrue(legal.permitted(new, automatic=True))
        changed = {**new,"license":{**new["license"],"sha256":"d"*64}}
        self.assertFalse(legal.permitted(changed, automatic=True))

    def test_game_update_notifies_then_installs_after_restart_consent_and_preserves_saves(self):
        self.app.finish_notice({'accepted':True})
        self.app.save_preferences({'launcher_repo':''})
        sid,ident=self.add_fixture()
        first=tar_bytes({'Game/run.sh':'#!/bin/sh\nexit 0\n','Game/version.txt':'one'})
        with patch('recopile.service.latest_release',return_value=release(first)),patch('recopile.network.open_url',side_effect=lambda *_a,**_k:io.BytesIO(first)):
            self.assertEqual(wait_job(self.app,self.reviewed_install(sid,ident))['status'],'completed')
        installed=self.app.store.get('installs',ident)
        save=Path(installed['user_root'])/'save.dat';save.write_text('keep my save')
        second=tar_bytes({'Game/run.sh':'#!/bin/sh\nexit 0\n','Game/version.txt':'two'})
        with patch('recopile.service.latest_release',return_value=release(second,'v1.1.0',published='2026-10-02T00:00:00Z')),patch('recopile.network.open_url',side_effect=lambda *_a,**_k:io.BytesIO(second)):
            self.assertEqual(wait_job(self.app,self.app.check_updates())['status'],'completed')
            pending=next(p for p in self.app.store.get('settings','pending_updates') if p['target']==ident)
            self.assertTrue(pending['notify_only'])
            self.assertEqual(self.app.store.get('installs',ident)['version'],'v1.0.0')
            self.assertEqual(self.app.apply_pending_updates(),[])
            self.app.documents.seen(pending['documents']['fingerprint'])
            queued=self.app.apply_pending_updates()
            self.assertEqual(len(queued),1)
            self.assertEqual(wait_job(self.app,queued[0])['status'],'completed')
        self.assertEqual(self.app.store.get('installs',ident)['version'],'v1.1.0')
        self.assertEqual(save.read_text(),'keep my save')
        self.assertTrue(Path(installed['runtime_dir']).is_dir())
        self.assertEqual(self.app.store.get('settings','pending_updates'),[])

    def test_install_rejects_readme_review_without_separate_license_acceptance(self):
        sid, ident = self.add_fixture()
        with patch('recopile.service.latest_release', return_value=release(b'fixture')), patch('recopile.service.download') as downloader:
            docs = self.app.install(sid, ident)['documents']
            for consent in ({}, {'license_accepted':False}, {'license_accepted':'yes'},
                            {'license_accepted':True, 'license_hash':'old-license'}):
                with self.subTest(consent=consent), self.assertRaises(UserError):
                    self.app.install(sid, ident, review=docs['fingerprint'], **consent)
        downloader.assert_not_called()
        self.assertFalse(self.app.jobs.list())
        self.assertIsNone(self.app.store.get('settings', 'consent:example/game'))

    def test_missing_license_and_old_combined_consent_cannot_authorize_installation(self):
        docs = fixture_documents({'repo':'example/game','name':'Test'}, release(b'x'))
        legal = self.app.documents
        self.app.store.put('settings','consent:example/game',{'fingerprint':docs['fingerprint'],
            'license_hash':docs['license']['sha256'], 'auto':True})
        self.assertFalse(legal.permitted(docs))
        self.assertFalse(legal.permitted(docs, automatic=True))
        for license_doc in ({**docs['license'],'available':False}, {**docs['license'],'text':'  '},
                            {**docs['license'],'sha256':''}):
            missing={**docs,'license':license_doc}
            with self.subTest(license_doc=license_doc), self.assertRaises(UserError):
                legal.accept(missing, missing['fingerprint'], license_accepted=True, license_hash=license_doc['sha256'])
        accepted=legal.accept(docs,docs['fingerprint'],license_accepted=True,license_hash=docs['license']['sha256'])
        self.assertTrue(accepted['license_accepted'])
        self.assertTrue(legal.permitted(docs))
        self.assertFalse(legal.permitted(docs,automatic=True))
        # Even a cached identical fingerprint cannot authorize an absent or altered license.
        self.assertFalse(legal.permitted({**docs,'license':{**docs['license'],'available':False}}))
        self.assertFalse(legal.permitted({**docs,'license':{**docs['license'],'sha256':'changed'}}))

    def test_profiles_keep_activity_separate_and_export_real_data(self):
        game = self.app.require_game(game_id("xbox360","Forza Horizon"))
        self.app.profiles.record("local",game,3601,0)
        second = self.app.profiles.create("Drugi gracz")
        self.app.profiles.switch(second["id"])
        self.assertEqual(self.app.profiles.summary()["seconds"],0)
        self.assertEqual(self.app.profiles.summary("local")["seconds"],3601)
        self.app.profiles.switch("local")
        self.assertEqual(len(self.app.profiles.summary()["achievements"]),2)
        output = self.app.profiles.export_png()
        self.assertTrue(output["base64"].startswith("iVBOR"))
        self.assertEqual(output["summary"]["profile"]["name"],"Gracz")

    def test_compatibility_requires_approved_matching_device_reports(self):
        self.app.save_preferences({'launcher_repo':''})
        game = self.app.detail(game_id("xbox360","Forza Horizon"))
        c = self.app.compatibility
        self.assertEqual(game["compatibility"]["status"],"unknown")
        result = c.submit_local(game,{"status":"playable","notes":"Testowy raport","fps":60},self.app.preferences())
        self.assertIsNone(result["issue_url"])
        self.assertEqual(c.describe(game)["status"],"unknown")
        report = {**result["report"],"approved":True,"device_fingerprint":"another device"}
        self.app.store.put("settings","public_compatibility",{"schema_version":1,"reports":[report]})
        self.assertEqual(c.describe(game)["status"],"unknown")
        self.assertEqual(c.describe(game)["system_reports"],1)
        report["device_fingerprint"] = c.device["fingerprint"]
        self.app.store.put("settings","public_compatibility",{"schema_version":1,"reports":[report]})
        self.assertEqual(c.describe(game)["status"],"playable")

    def test_desktop_cannot_enable_ads(self):
        self.app.save_preferences({"android_ads":True})
        self.assertFalse(self.app.preferences()["android_ads"])

    def test_first_launch_needs_license_acknowledgment(self):
        notice=self.app.bootstrap()['app_notice']
        self.assertEqual(notice['license_name'],'GNU GPLv3')
        self.assertIn('GNU GENERAL PUBLIC LICENSE',notice['license'])
        with self.assertRaises(UserError): self.app.finish_notice({"accepted":False})
        self.app.finish_notice({"accepted":True})
        self.assertFalse(self.app.bootstrap()["app_notice"]["required"])
        # An old acknowledgment of reading the text is not the new explicit acceptance.
        prefs=self.app.preferences()
        prefs.pop('app_license_accepted',None)
        self.app.store.put('settings','preferences',prefs)
        self.assertTrue(self.app.bootstrap()['app_notice']['required'])
        self.app.finish_notice({'accepted':True})
        self.app.store.put('settings','preferences',{**self.app.preferences(),'accepted_app_license':'previous-custom-license-hash'})
        self.assertTrue(self.app.bootstrap()['app_notice']['required'])

    def test_local_executable_is_launched_without_a_shell(self):
        program = self.root / "game ; not-a-command"
        program.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\nPath('ran.txt').write_text('ok')\n")
        program.chmod(0o755)
        game = self.app.add_local_game({"title": "Local Test", "path": str(program), "trusted": True})
        self.app.launch(game["id"])
        deadline = time.monotonic() + 5
        while self.app.active_processes() and time.monotonic() < deadline:
            time.sleep(.03)
        self.assertEqual((self.root / "ran.txt").read_text(), "ok")
        self.app.save_preferences({"only_recompiled": True})
        with self.assertRaises(UserError):
            self.app.launch(game["id"])

    def test_invalid_source_does_not_leave_partial_database_writes(self):
        before = len(self.app.store.list("sources"))
        with self.assertRaises(UserError):
            self.app.add_source({"repo": "example/game", "name": "Fixture", "title": "Wrong", "platform": "ps2", "kind": "native", "asset_pattern": "*.zip", "trusted": True, "game_id": game_id("xbox360", "Halo 3")})
        self.assertEqual(len(self.app.store.list("sources")), before)

    def test_dump_rejects_unsupported_platform_without_accessing_device(self):
        with self.assertRaises(UserError):
            self.app.dump_disc({"platform": "xbox360", "owned": True, "device": "/dev/sda", "filename": "game.iso"})

    def test_launcher_update_is_staged_and_not_executed(self):
        self.app.save_preferences({"launcher_repo": "example/recopile"})
        payload = tar_bytes({"Recopile/launcher.py": "# deferred", "Recopile/recopile/server.py": "# fixture", "Recopile/frontend/dist/client/index.html": "fixture", "Recopile/data/catalog.json.gz": b"fixture"})
        with patch("recopile.service.latest_release", return_value=release(payload, "v99.0.0", "Recopile-0.2.0-linux-x86_64.tar.gz")), patch("recopile.network.open_url", return_value=io.BytesIO(payload)):
            result = wait_job(self.app, self.app.stage_launcher_update())
        self.assertEqual(result["status"], "completed", result.get("message"))
        marker = json.loads((self.root / "state/pending-launcher.json").read_text())
        self.assertTrue(Path(marker["root"]).is_relative_to(self.root / "state/launcher-updates"))
        self.assertEqual(marker["version"], "v99.0.0")

    def test_http_origin_token_and_path_security(self):
        server = create_server(self.app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/api/bootstrap") as response:
                token = json.load(response)["token"]
            request = Request(base + "/api/settings", data=b'{"only_recompiled":true}', headers={"Content-Type": "application/json", "X-Recopile-Token": token})
            with urlopen(request):
                pass
            with urlopen(base + "/api/games") as response:
                self.assertEqual(json.load(response)["total"], 5)
            for headers in [{"X-Recopile-Token": "bad"}, {"X-Recopile-Token": token, "Origin": "https://evil.example"}, {"X-Recopile-Token": token, "Host": "evil.example"}]:
                request = Request(base + "/api/settings", data=b"{}", headers={"Content-Type": "application/json", **headers})
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request)
                self.assertEqual(raised.exception.code, 403)
            with self.assertRaises(HTTPError) as raised:
                urlopen(base + "/%2e%2e/data/registry.json")
            self.assertEqual(raised.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
