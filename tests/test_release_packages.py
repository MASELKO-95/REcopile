"""Component releases and public source-tools installation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from recopile.network import extract, latest_release, version_key
from recopile.registry import validate_registry
from recopile.service import Launcher
from recopile.storage import game_id

ROOT = Path(__file__).resolve().parents[1]


class ComponentReleaseTests(unittest.TestCase):
    def test_beta_and_stable_semver_ordering(self):
        versions = ['0.2.2-beta.1', '0.2.2-beta.2', '0.2.2-beta.10', '0.2.2', '0.2.3-beta.1', '0.2.3']
        self.assertEqual(sorted(reversed(versions), key=version_key), versions)
        self.assertEqual(version_key('v0.2.2'), version_key('0.2.2'))

    def test_launcher_ignores_a_newer_port_tools_release(self):
        asset = lambda name: {'name': name, 'size': 123, 'browser_download_url': 'https://github.com/MASELKO-95/recopile/releases/download/fixture/'+name}
        releases = [
            {'tag_name': 'pinyon-v0.6.0-recopile.1', 'html_url': 'https://github.com/MASELKO-95/recopile/releases', 'assets': [asset('Pinyon-tools.tar.gz')]},
            {'tag_name': 'v0.2.2-beta.2', 'prerelease': True, 'html_url': 'https://github.com/MASELKO-95/recopile/releases', 'assets': [asset('Recopile-0.2.2-beta.2-linux-x86_64.AppImage')]},
            {'tag_name': 'v0.2.1', 'html_url': 'https://github.com/MASELKO-95/recopile/releases', 'assets': [asset('Recopile-0.2.1-linux-x86_64.AppImage')]},
        ]
        source = {'repo': 'MASELKO-95/recopile', 'asset_pattern': 'Recopile-*-linux-x86_64.AppImage', 'scan_releases': True}
        with patch('recopile.network.fetch_json', return_value=releases):
            self.assertEqual(latest_release(source)['version'], 'v0.2.1')
            self.assertEqual(latest_release({**source, 'allow_prerelease': True})['version'], 'v0.2.2-beta.2')

    def test_pinned_component_is_not_confused_with_the_hub_release(self):
        release = {'tag_name': 'pinyon-v0.6.0-recopile.1', 'html_url': 'https://github.com/MASELKO-95/recopile/releases/tag/pinyon-v0.6.0-recopile.1',
                   'assets': [{'name': 'Pinyon-tools.tar.gz', 'browser_download_url': 'https://github.com/MASELKO-95/recopile/releases/download/pinyon-v0.6.0-recopile.1/Pinyon-tools.tar.gz', 'size': 123}]}
        with patch('recopile.network.fetch_json', return_value=release) as request:
            selected = latest_release({'repo': 'MASELKO-95/recopile', 'release_tag': release['tag_name'], 'asset_pattern': 'Pinyon-tools.tar.gz'})
        self.assertTrue(request.call_args.args[0].endswith('/releases/tags/pinyon-v0.6.0-recopile.1'))
        self.assertEqual(selected['version'], release['tag_name'])

    def test_registry_routes_linux_tools_and_preserves_windows_upstream(self):
        registry = json.loads((ROOT / 'data/registry.json').read_text())
        validate_registry(registry)
        with tempfile.TemporaryDirectory() as folder:
            app = Launcher(ROOT, Path(folder) / 'state', automatic=False)
            try:
                source = app.source('pinyon')
                with patch.object(app, 'system_key', return_value='linux'):
                    linux = app.target_source(source)
                self.assertEqual(linux['repo'], 'MASELKO-95/recopile')
                self.assertEqual(linux['release_tag'], 'pinyon-v0.6.0-recopile.1')
                self.assertEqual(linux['documentation_repo'], 'arcanite24/pinyon-shift')
                with patch.object(app, 'system_key', return_value='windows'):
                    windows = app.target_source(source)
                self.assertEqual(windows['repo'], 'arcanite24/pinyon-shift')
                self.assertNotIn('release_tag', windows)
            finally:
                app.shutdown(); app.jobs.pool.shutdown(wait=True); app.media.pool.shutdown(wait=True)

    def test_real_public_tools_archive_imports_and_runs_upstream_help(self):
        package = ROOT / 'artifacts/desktop/PinyonShift-0.6.0-Recopile-linux-x86_64.tar.gz'
        if not package.is_file(): self.skipTest('Build the Pinyon tools archive to test this integration.')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            runtime = base / 'runtime'
            extract(package, runtime, package.name)
            app = Launcher(ROOT, base / 'state', automatic=False)
            try:
                install = {'game_root': str(base / 'game'), 'runtime_dir': str(runtime),
                           'version': 'pinyon-v0.6.0-recopile.1', 'source_id': 'pinyon'}
                source = app.port_setup.ensure_source(install)
                release = json.loads((source / 'config/release.json').read_text())
                self.assertEqual(release['version'], '0.6.0')
                self.assertEqual((source / 'LICENSE').read_bytes(), (ROOT / 'ports/pinyon/UPSTREAM-LICENSE').read_bytes())
                result = subprocess.run([sys.executable, str(source / 'tools/pinyon.py'), '--help'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('setup', result.stdout)
                result = subprocess.run([sys.executable, str(runtime / 'PinyonShift/PinyonShift-Recopile.py'), '--help'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((source / '.local/game').exists())
            finally:
                app.shutdown(); app.jobs.pool.shutdown(wait=True); app.media.pool.shutdown(wait=True)
