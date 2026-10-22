"""Author-hosted downloads remain distinct from the automatic GitHub installer."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recopile.network import UserError
from recopile.platforms import device_options
from recopile.registry import entry, validate_registry
from recopile.service import Launcher
from recopile.storage import game_id

ROOT = Path(__file__).resolve().parents[1]


class ExternalDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='recopile-author-download-')
        self.app = Launcher(ROOT, Path(self.temp.name), automatic=False)
        self.ident = game_id('xboxone', 'Forza Horizon 2')
        self.source = self.app.source('fh2-azimuth')

    def tearDown(self):
        self.app.shutdown()
        self.app.media.pool.shutdown(wait=True)
        self.app.jobs.pool.shutdown(wait=True)
        self.temp.cleanup()

    def test_author_page_and_platform_identity_survive_export_and_offline_restart(self):
        exported = entry(self.source, self.app.detail(self.ident))['sources'][0]
        self.assertEqual(exported['download_page'], 'https://almost-there-games.itch.io/azimuth')
        self.assertEqual(exported['author'], 'Almost There Games')
        self.assertEqual(exported['manual_systems'], ['windows'])
        self.app.store._seed()
        self.assertEqual(self.app.source('fh2-azimuth')['download_page'], exported['download_page'])
        self.assertNotIn('fh2-azimuth', self.app.detail(game_id('xbox360', 'Forza Horizon 2'))['source_ids'])

    def test_manual_windows_download_is_visible_on_windows_and_via_proton_on_linux(self):
        game = self.app.detail(self.ident)
        for system, via in [('windows', 'native'), ('linux', 'proton')]:
            with self.subTest(system=system), patch.object(self.app, 'system_key', return_value=system):
                self.assertEqual(device_options(game, system), [{'system': 'windows', 'via': via, 'source_id': 'fh2-azimuth', 'manual': True}])
                self.assertEqual(self.app.query(q='Forza Horizon 2', platform='xboxone', view='device')['total'], 1)
        self.assertFalse(device_options(game, 'android'))

    def test_install_and_document_routes_do_not_request_github_for_external_sources(self):
        with patch('recopile.service.latest_release') as release, patch('recopile.service.fetch_json') as fetch:
            for call in [lambda: self.app.install('fh2-azimuth', self.ident), lambda: self.app.project_information('fh2-azimuth')]:
                with self.assertRaisesRegex(UserError, 'https://almost-there-games.itch.io/azimuth'):
                    call()
            release.assert_not_called()
            fetch.assert_not_called()
        self.assertFalse(self.app.jobs.list())

    def test_update_check_skips_external_distribution_without_a_failed_download_job(self):
        self.app.save_preferences({'launcher_repo': ''})
        original = self.app.store.list
        with patch.object(self.app.store, 'list', side_effect=lambda table: [self.source] if table == 'sources' else original(table)), patch.object(self.app, 'release') as release:
            self.app.check_updates()
            self.app.jobs.pool.shutdown(wait=True)
            release.assert_not_called()
        result = self.app.jobs.list()[0]
        self.assertEqual(result['status'], 'completed', result)

    def test_invalid_and_temporary_download_urls_are_rejected(self):
        for page in ['http://example.com/download', 'https://user:secret@example.com/file', 'https://example.com/file?token=secret', 'https://[broken', 'https://example.com/a b', 'javascript:alert(1)']:
            source = {**self.source, 'download_page': page}
            with self.subTest(page=page), self.assertRaises(UserError):
                validate_registry(entry(source, self.app.detail(self.ident)))

    def test_external_source_cannot_enable_automatic_updates_or_github_assets(self):
        for fields in [{'auto_update': True}, {'asset_pattern': '*.zip'}, {'assets_by_system': {'windows': '*.zip'}}, {'manual_systems': []}]:
            with self.subTest(fields=fields), self.assertRaises(UserError):
                entry({**self.source, **fields}, self.app.detail(self.ident))
