from __future__ import annotations

import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from recopile.media import validate_media_url, wikipedia_metadata
from recopile.network import UserError
from recopile.registry import validate_registry
from recopile.server import create_server
from recopile.service import Launcher
from recopile.storage import game_id
from tools.build_catalog import XboxOneTable

ROOT = Path(__file__).resolve().parents[1]
METADATA = {"description": "Forza Horizon 3 is a 2016 racing game.",
    "description_url": "https://en.wikipedia.org/wiki/Forza_Horizon_3", "description_license": "CC BY-SA 4.0",
    "thumbnail": "https://upload.wikimedia.org/wikipedia/en/a/ab/Cover.png"}


def artwork():
    stream = io.BytesIO()
    Image.new("RGB", (20, 30), "purple").save(stream, "PNG")
    return stream.getvalue()


class CatalogMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="recopile-media-test-")
        self.app = Launcher(ROOT, Path(self.tmp.name) / "state", automatic=False)
        self.ident = game_id("xboxone", "Forza Horizon 3")

    def tearDown(self):
        self.app.shutdown()
        self.app.media.pool.shutdown(wait=True)
        self.app.jobs.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def wait_media(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with self.app.media.lock:
                if not self.app.media.pending: return
            time.sleep(.01)
        self.fail("Media task did not finish")

    def request(self, covers=False):
        return self.app.request_media({"game_ids": [self.ident], "covers": covers})

    def test_xbox_one_catalog_is_separate_and_does_not_invent_a_launch_adapter(self):
        result = self.app.query(q="Forza Horizon 3", platform="xboxone")
        self.assertEqual(result["total"], 1)
        game = self.app.detail(self.ident)
        self.assertEqual(game["kind"], "catalog")
        self.assertFalse(game["sources"])
        self.assertIsNone(game["engine"])
        self.assertFalse(game["device_options"])
        self.assertTrue(game["genre"])
        self.assertTrue(self.app.query(q="Forza Horizon", platform="xbox360")["games"])

    def test_browsing_and_opening_details_do_not_fetch_artwork(self):
        with patch("recopile.media.read_media") as remote:
            self.app.bootstrap()
            self.app.query(platform="xboxone")
            self.app.query(q="Forza Horizon 3")
            self.app.detail(self.ident)
        remote.assert_not_called()
        self.assertFalse((self.app.store.root / "covers").exists())

    def test_description_loads_without_downloading_cover_and_survives_restart(self):
        with patch("recopile.media.wikipedia_metadata", return_value=METADATA), patch("recopile.media.read_media") as remote:
            self.request()
            self.wait_media()
            remote.assert_not_called()
        game = self.app.detail(self.ident)
        self.assertEqual(game["description"], METADATA["description"])
        self.assertNotIn("cover_url", game)
        self.assertFalse((self.app.store.root / "covers").exists())
        self.app.shutdown()
        self.app.media.pool.shutdown(wait=True)
        with patch("recopile.media.wikipedia_metadata") as metadata:
            self.app = Launcher(ROOT, self.app.store.root, automatic=False)
            self.request()
            self.wait_media()
            self.assertEqual(self.app.detail(self.ident)["description"], METADATA["description"])
            metadata.assert_not_called()

    def test_explicit_cover_download_is_cached_and_fails_independently_of_description(self):
        with patch("recopile.media.wikipedia_metadata", return_value=METADATA), patch("recopile.media.read_media", side_effect=OSError("offline")):
            self.request(covers=True)
            self.wait_media()
        game = self.app.detail(self.ident)
        self.assertEqual(game["description"], METADATA["description"])
        self.assertEqual(game["media_status"]["cover"], "error")
        cache = self.app.store.get("game_media", self.ident)
        self.app.store.put("game_media", self.ident, {**cache, "cover_checked": 1})
        with patch("recopile.media.wikipedia_metadata") as metadata, patch("recopile.media.read_media", return_value=artwork()) as image:
            self.request(covers=True)
            self.wait_media()
            self.request(covers=True)
            self.wait_media()
            metadata.assert_not_called()
            image.assert_called_once()
        game = self.app.detail(self.ident)
        self.assertTrue(game["cover_url"].startswith("/api/covers/"))
        self.assertTrue((self.app.store.root / "covers" / game["cover_url"].rsplit("/", 1)[-1]).is_file())

    def test_missing_metadata_is_cached_and_untrusted_image_hosts_are_rejected(self):
        with patch("recopile.media.wikipedia_metadata", return_value={}) as metadata, patch("recopile.media.read_media") as remote:
            self.request(covers=True)
            self.wait_media()
            self.request(covers=True)
            self.wait_media()
            metadata.assert_called_once()
            remote.assert_not_called()
        for url in ["http://upload.wikimedia.org/a.png", "https://127.0.0.1/a.png", "https://upload.wikimedia.org.evil.test/a.png", "https://user:pass@en.wikipedia.org/wiki/Game"]:
            with self.subTest(url=url), self.assertRaises(UserError): validate_media_url(url)

    def test_text_only_request_can_be_upgraded_while_in_flight(self):
        started, resume = threading.Event(), threading.Event()
        def fetch(_):
            started.set()
            self.assertTrue(resume.wait(3))
            return METADATA
        with patch("recopile.media.wikipedia_metadata", side_effect=fetch) as metadata, patch("recopile.media.read_media", return_value=artwork()) as image:
            self.request()
            self.assertTrue(started.wait(3))
            self.request(covers=True)
            resume.set()
            self.wait_media()
            metadata.assert_called_once()
            image.assert_called_once()
        self.assertIn("cover_url", self.app.detail(self.ident))

    def test_manual_request_only_enriches_selected_games_and_validates_entire_batch(self):
        with patch("recopile.media.wikipedia_metadata", return_value=METADATA) as metadata, patch("recopile.media.read_media", return_value=artwork()):
            self.request(covers=True)
            self.wait_media()
            self.assertEqual(metadata.call_args.args[0]["id"], self.ident)
            self.assertEqual(len(self.app.store.list("game_media")), 1)
            for ids in [[], [self.ident] * 13, [self.ident, "not-a-game"]]:
                with self.subTest(ids=ids), self.assertRaises(UserError):
                    self.app.request_media({"game_ids": ids, "covers": True})
            self.assertEqual(len(self.app.store.list("game_media")), 1)

    def test_invalid_artwork_does_not_replace_the_description_or_create_a_file(self):
        with patch("recopile.media.wikipedia_metadata", return_value=METADATA), patch("recopile.media.read_media", return_value=b"<html>not an image</html>"):
            self.request(covers=True)
            self.wait_media()
        game = self.app.detail(self.ident)
        self.assertEqual(game["description"], METADATA["description"])
        self.assertNotIn("cover_url", game)
        self.assertEqual(game["media_status"]["cover"], "error")
        self.assertFalse((self.app.store.root / "covers").exists())

    def test_local_games_including_xbox_one_links_follow_the_executable_system(self):
        local_ids = {}
        for system, contents in [("linux", b"#!/bin/sh\nexit 0\n"), ("windows", b"MZ" + b"\0" * 64)]:
            path = Path(self.tmp.name) / ("local-" + system + (".exe" if system == "windows" else ".sh"))
            path.write_bytes(contents)
            path.chmod(0o755)
            game = self.app.add_local_game({"title": "Local fixture " + system, "platform": "xboxone", "path": str(path), "trusted": True})
            local_ids[system] = game["id"]
        for system, expected in [("linux", set(local_ids.values())), ("windows", {local_ids["windows"]}), ("android", set())]:
            with self.subTest(system=system), patch.object(self.app, "system_key", return_value=system):
                result = self.app.query(q="Local fixture", view="device")
                self.assertEqual({g["id"] for g in result["games"]}, expected)
        self.assertEqual(self.app.detail(local_ids["linux"])["kind"], "native")

    def test_cached_cover_http_endpoint_checks_token_and_file_path(self):
        server = create_server(self.app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            with urlopen(base + "/api/bootstrap") as response: token = json.load(response)["token"]
            body = json.dumps({"game_ids": [self.ident], "covers": True}).encode()
            with self.assertRaises(HTTPError) as rejected:
                urlopen(Request(base + "/api/media", data=body, headers={"Content-Type": "application/json"}))
            rejected.exception.close()
            raw = artwork()
            with patch("recopile.media.wikipedia_metadata", return_value=METADATA), patch("recopile.media.read_media", return_value=raw):
                with urlopen(Request(base + "/api/media", data=body, headers={"Content-Type": "application/json", "X-Recopile-Token": token})) as response:
                    self.assertEqual(response.status, 200)
                self.wait_media()
            with urlopen(base + self.app.detail(self.ident)["cover_url"]) as response:
                self.assertEqual(response.headers["Content-Type"], "image/png")
                self.assertEqual(response.read(), raw)
            with self.assertRaises(HTTPError) as rejected: urlopen(base + "/api/covers/..%2Flibrary.sqlite3")
            rejected.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_device_filter_applies_before_count_and_pagination(self):
        ids = {}
        for system in ["linux", "windows", "android"]:
            value = self.app.add_source({"repo": "example/game", "name": system, "title": "Device fixture " + system,
                "platform": "other", "kind": "native", "asset_pattern": "Game.zip", "executable": "game",
                "assets_by_system": {system: "Game.zip"}, "trusted": True})
            ids[system] = value["game"]["id"]
        for system, expected in [("linux", {ids["linux"], ids["windows"]}), ("windows", {ids["windows"]}), ("android", {ids["android"]})]:
            with self.subTest(system=system), patch.object(self.app, "system_key", return_value=system):
                result = self.app.query(q="Device fixture", view="device")
                self.assertEqual({g["id"] for g in result["games"]}, expected)
                page = self.app.query(q="Device fixture", view="device", limit=1, offset=1)
                self.assertEqual(page["total"], len(expected))
                self.assertEqual(len(page["games"]), max(0, len(expected) - 1))
                self.assertFalse(self.app.query(q="Device fixture", view="installed", device_only=True)["games"])
                if system == "linux":
                    windows = next(g for g in result["games"] if g["id"] == ids["windows"])
                    self.assertEqual(windows["device_options"][0]["via"], "proton")
        with patch.object(self.app, "system_key", return_value="windows"):
            source_id = self.app.store.game(ids["linux"])["source_ids"][0]
            with self.assertRaises(UserError):
                self.app.target_source(self.app.store.get("sources", source_id))


class MetadataParsingTests(unittest.TestCase):
    def test_xbox_table_ignores_navigation_and_preserves_game_metadata(self):
        parser = XboxOneTable()
        parser.feed('<table><tr><td>Ignore</td></tr></table><table id="softwarelist"><tr><th>Title</th></tr><tr><td><i><a href="/wiki/Example_Game">Example Game</a></i><sup>[1]</sup></td><td>Racing</td><td>A<br>B</td><td>C</td><td>2016</td><td>2016</td><td>Unreleased</td></tr></table>')
        self.assertEqual(len(parser.rows), 1)
        cells, link = parser.rows[0]
        self.assertEqual(cells[:4], ["Example Game", "Racing", "A, B", "C"])
        self.assertEqual(link, "https://en.wikipedia.org/wiki/Example_Game")

    def test_disambiguation_page_is_not_used_as_game_description(self):
        pages = [{"title": "Example", "extract": "A video game series.", "pageprops": {"disambiguation": ""}},
            {"title": "Example (video game)", "extract": "Example is a racing video game.", "pageprops": {}}]
        with patch("recopile.media.read_media", return_value=json.dumps({"query": {"pages": pages}}).encode()):
            result = wikipedia_metadata({"title": "Example"})
        self.assertEqual(result["description"], "Example is a racing video game.")
        self.assertIn("Example_%28video_game%29", result["description_url"])

    def test_registry_accepts_xbox_one_sources(self):
        value = {"schema_version": 1, "sources": [{"id": "sample", "name": "Sample", "repo": "example/game",
            "platform": "xboxone", "kind": "native", "asset_pattern": "Game.zip", "executable": "game"}],
            "featured": [{"title": "Example", "platform": "xboxone", "source_ids": ["sample"]}]}
        self.assertIs(validate_registry(value), value)
