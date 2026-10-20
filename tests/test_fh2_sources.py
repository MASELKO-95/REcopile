from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recopile.network import UserError
from recopile.service import Launcher
from recopile.storage import game_id
from tools.update_port_list import render

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("fh2-recomp", "fh2-recomp-shreyash", "fh2-recomp-maselko")


class ForzaHorizonTwoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="recopile-fh2-test-")
        self.app = Launcher(ROOT, Path(self.tmp.name), automatic=False)
        self.ident = game_id("xbox360", "Forza Horizon 2")

    def tearDown(self):
        self.app.shutdown()
        self.app.media.pool.shutdown(wait=True)
        self.app.jobs.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def test_experimental_sources_belong_only_to_xbox_360_and_preserve_catalog_variants(self):
        game = self.app.detail(self.ident)
        self.assertEqual(game["kind"], "recompile")
        self.assertEqual(game["development_status"], "in_progress")
        self.assertEqual([s["id"] for s in game["sources"]], list(SOURCES))
        self.assertGreater(game["variant_count"], 0)
        xbox_one = self.app.detail(game_id("xboxone", "Forza Horizon 2"))
        self.assertEqual(xbox_one["kind"], "catalog")
        self.assertFalse(xbox_one["sources"])

    def test_experiments_have_no_installable_package_or_host_view_entry(self):
        with patch("recopile.service.latest_release") as release:
            for sid in SOURCES:
                source = self.app.source(sid)
                self.assertFalse(source["assets_by_system"])
                self.assertFalse(source["auto_update"])
                self.assertEqual(source["experimental_systems"], ["windows", "linux"] if sid == "fh2-recomp-maselko" else ["windows"])
                with self.assertRaises(UserError): self.app.install(sid, self.ident)
            release.assert_not_called()
        for system in ("linux", "windows"):
            with self.subTest(system=system), patch.object(self.app, "system_key", return_value=system):
                self.assertEqual(self.app.query(q="Forza Horizon 2", platform="xbox360", view="device")["total"], 0)
        self.assertFalse(self.app.jobs.list())

    def test_remote_development_information_fetches_each_repos_actual_readme_at_a_commit(self):
        for sid in SOURCES:
            source = self.app.source(sid)
            repo = source["repo"]
            base = "https://api.github.com/repos/" + repo
            sha = "1" * 40
            upstream_text = "# Forza Horizon 2 Recompiled\nWindows loading-screen experiment from " + repo
            requests = []
            def remote(url):
                requests.append(url)
                if url == base: return {"default_branch": "main"}
                if url == base + "/commits/main": return {"sha": sha}
                if url == base + "/readme?ref=" + sha:
                    return {"encoding": "base64", "content": base64.b64encode(upstream_text.encode()).decode(),
                        "name": "README.md", "size": len(upstream_text), "html_url": "https://github.com/" + repo + "/blob/" + sha + "/README.md"}
                raise UserError("No root license or funding file in this fixture")
            with self.subTest(source=sid), patch("recopile.service.fetch_json", side_effect=remote), patch("recopile.legal.fetch_json", side_effect=remote), patch.object(self.app, "local_project_information") as local:
                result = self.app.project_information(sid)
            local.assert_not_called()
            self.assertEqual(result["repo"], repo)
            self.assertEqual(result["version"], sha)
            self.assertEqual(result["readme"]["text"], upstream_text)
            self.assertEqual(result["asset_size"], 0)
            self.assertFalse(result["license"]["available"])
            self.assertIn(base + "/contents/LICENSE?ref=" + sha, requests)
            self.assertFalse(any("rexglue-sdk/LICENSE" in url for url in requests), "The SDK license must not be presented as a root project license")

    def test_editing_a_development_repo_without_packages_keeps_it_experimental(self):
        source = self.app.update_source(SOURCES[0], {"name": "My FH2 research", "trusted": True})
        self.assertEqual(source["origin"], "development")
        self.assertTrue(source["user_override"])
        self.assertFalse(source["assets_by_system"])
        with self.assertRaises(UserError): self.app.install(SOURCES[0], self.ident)

    def test_generated_port_list_separates_local_linux_experiment_from_packages(self):
        registry = json.loads((ROOT / "data/registry.json").read_text())
        rows = [line for line in render(registry).splitlines() if line.startswith("| Forza Horizon 2 Recompiled")]
        self.assertGreaterEqual(len(rows), 2)
        for row in rows:
            columns = row.split("|")
            self.assertEqual(columns[3].strip(), "Experiment only; no package" if "MASELKO-95" in columns[2] else "No declared package")
            self.assertEqual(columns[4].strip(), "Experiment only; no package")
