"""List imports, offline state, source preservation and declared packages.

Copyright (C) 2026 MASELKO-95. GPL-3.0-only. Added 2026-10-30.
"""
import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recopile.catalog_lists import LISTS, GuideLinks, fetch_list, parse_html, parse_markdown, repo_link
from recopile.network import Cancelled, UserError, latest_release
from recopile.registry import validate_registry
from recopile.service import Launcher
from recopile.storage import Store, game_id

ROOT=Path(__file__).resolve().parents[1]
MD='| Game | Description | Author |\n| [New Test Game](https://github.com/example/new-port) | Sample | [Owner](https://github.com/example) |\n'
HTML='<table><tr><td class="r-game">Other Test Game<div class="r-alias">Hidden alias</div><div class="r-note">Hidden note</div></td><td>Xbox 360</td><td>OtherPort</td><td><a href="https://github.com/example/other-port">Project</a></td></tr></table>'


class ListParsingTests(unittest.TestCase):
    def test_markdown_reads_game_table_only(self):
        text=MD+'\n- [Not a game](https://github.com/example/sdk)\n'
        self.assertEqual(parse_markdown(text),[{'title':'New Test Game','repo':'example/new-port'}])

    def test_html_does_not_append_aliases_notes_or_unrelated_links(self):
        self.assertEqual(parse_html(HTML+'<a href="https://github.com/example/sdk">SDK</a>'),
                         [{'title':'Other Test Game','repo':'example/other-port'}])

    def test_internal_guide_resolves_the_matching_project(self):
        html='<tr><td>Sample Game</td><td>Xbox 360</td><td>SecondPort</td><td><a href="/sample-game-pc/">Guide</a></td></tr>'
        entries=parse_html(html,{'https://portedgames.com/sample-game-pc/':['example/FirstPort','other/SecondPort']})
        self.assertEqual(entries,[{'title':'Sample Game','repo':'other/SecondPort'}])

    def test_empty_or_changed_pages_do_not_replace_cached_lists(self):
        for parser in (parse_html,parse_markdown):
            with self.assertRaises(UserError):parser('<h1>Temporary error</h1>')

    def test_links_cannot_be_commands_credentials_or_other_hosts(self):
        for url in ('http://github.com/a/b','https://github.com.evil.test/a/b','https://github.com/a/b?token=secret',
                    'https://user:password@github.com/a/b','https://github.com/a/b/releases','https://[invalid'):
            self.assertIsNone(repo_link(url))
        with self.assertRaises(UserError):fetch_list({'feed':'https://example.test/private'})

    def test_port_release_tags_need_not_be_launcher_semver(self):
        asset=lambda name:{'name':name,'browser_download_url':'https://github.com/example/port/releases/download/recomp/'+name}
        releases=[{'tag_name':'android-alpha9','html_url':'https://github.com/example/port/releases','assets':[asset('game.apk')]},
                  {'tag_name':'recomp','html_url':'https://github.com/example/port/releases','assets':[asset('port-Windows.zip')]}]
        with patch('recopile.network.fetch_json',return_value=releases):
            release=latest_release({'repo':'example/port','kind':'recompile','asset_pattern':'port-Windows.zip','scan_releases':True})
        self.assertEqual(release['version'],'recomp')


class CatalogListTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='recopile-lists-')
        self.root=Path(self.temp.name)
        self.app=Launcher(ROOT,self.root/'state',automatic=False,scan_steam=False)
        self.app.save_preferences({'games_dir':str(self.root/'library'),'launcher_repo':''})

    def tearDown(self):
        self.app.shutdown();self.app.jobs.pool.shutdown(wait=True);self.app.media.pool.shutdown(wait=True)
        self.temp.cleanup()

    def test_sync_adds_sources_and_games_without_fetching_artwork_or_programs(self):
        with patch('recopile.catalog_lists.fetch_list',side_effect=[MD,HTML]),patch('recopile.service.download') as download,patch.object(self.app.media,'request') as media:
            result=self.app.catalog_lists.sync()
        self.assertEqual(result['added'],2);download.assert_not_called();media.assert_not_called()
        game=self.app.store.game(game_id('xbox360','New Test Game'))
        self.assertEqual(game['kind'],'recompile');self.assertFalse(game.get('added'))
        source=self.app.source(game['source_ids'][0])
        self.assertFalse(source.get('verified'));self.assertFalse(source.get('auto_update'));self.assertFalse(source['assets_by_system'])

    def test_list_matching_preserves_custom_sources_installs_profiles_and_order(self):
        game=self.app.store.game(game_id('xbox360','Forza Horizon'))
        before=copy.deepcopy(game)
        source=self.app.source('pinyon');source.update(user_override=True,note='My custom note')
        self.app.store.put('sources','pinyon',source)
        marker={'id':game['id'],'local_executable':'/private/existing-game','version':'custom'}
        self.app.store.put('installs',game['id'],marker)
        self.app.catalog_lists.include([{'title':'Forza Horizon','repo':source['repo']}],'awesome-x360')
        self.assertEqual(self.app.source('pinyon'),source)
        self.assertEqual(self.app.store.game(game['id']),before)
        self.assertEqual(self.app.store.get('installs',game['id']),marker)

    def test_offline_restart_retains_new_sources_and_last_successful_list(self):
        with patch('recopile.catalog_lists.fetch_list',side_effect=[MD,HTML]):self.app.catalog_lists.sync()
        first=self.app.store.get('settings','list:awesome-x360')
        with patch('recopile.catalog_lists.fetch_list',side_effect=UserError('Offline')):self.app.catalog_lists.sync()
        restarted=Store(ROOT,self.app.store.root)
        self.assertTrue(restarted.game(game_id('xbox360','New Test Game')))
        saved=restarted.get('settings','list:awesome-x360')
        self.assertEqual(saved['entries'],first['entries']);self.assertEqual(saved['checked_at'],first['checked_at'])
        self.assertEqual(saved['error'],'Offline')

    def test_missing_entry_can_be_added_from_cache_without_network(self):
        self.app.store.put('settings','list:awesome-x360',{'entries':[{'title':'New Test Game','repo':'example/new-port'}]})
        with patch('recopile.catalog_lists.fetch_list') as request:
            result=self.app.catalog_lists.add_cached({'list_id':'awesome-x360','repo':'example/new-port'})
        request.assert_not_called();self.assertEqual(result['game_id'],game_id('xbox360','New Test Game'))
        with self.assertRaises(UserError):self.app.catalog_lists.add_cached({'list_id':'awesome-x360','repo':'example/not-listed'})

    def test_cancel_does_not_discard_last_successful_snapshot(self):
        before=self.app.store.get('settings','list:awesome-x360')
        with self.assertRaises(Cancelled):self.app.catalog_lists.sync(cancelled=lambda:True)
        self.assertEqual(self.app.store.get('settings','list:awesome-x360'),before)

    def test_older_published_catalog_does_not_undo_newer_shipped_metadata(self):
        self.app.save_preferences({'launcher_repo':'example/catalog'})
        registry=json.loads((ROOT/'data/registry.json').read_text())
        registry['catalog_version']='2026-10-22.1';registry['sources'][0]['repo']='example/obsolete'
        with patch('recopile.service.fetch_json',return_value={'encoding':'base64','content':base64.b64encode(json.dumps(registry).encode()).decode()}):
            result=self.app.sync_catalog()
        self.assertTrue(result['older_catalog_ignored'])
        self.assertNotEqual(self.app.source(registry['sources'][0]['id'])['repo'],'example/obsolete')

    def test_registry_has_all_requested_games_with_separate_package_systems(self):
        registry=validate_registry(json.loads((ROOT/'data/registry.json').read_text()))
        for ident in ('futari','project8','tna-impact','rayman3-hd','madden08','wwe-svr2009','wwe-svr2010','wwe12','openjam','stuntman-ignition','naruto-rise','the-darkness','wet','earthworm-jim-hd','geometry-wars-2','vigilante8'):
            source=self.app.source(ident)
            self.assertFalse(source['auto_update']);self.assertEqual(source['platform'],'xbox360')
            self.assertTrue(source['assets_by_system'])
        self.assertNotIn('linux',self.app.source('wwe-svr2009')['assets_by_system'])
        self.assertEqual(len(registry['tracked_lists']),2)
        for item in self.app.catalog_lists.state()['lists']:self.assertEqual(item['missing'],0,item)

    def test_installer_cannot_be_mistaken_for_the_prepared_game(self):
        ident=game_id('xbox360','Madden NFL 08')
        self.app.store.put('installs',ident,{'id':ident,'adapter':'installer','setup_started_at':1})
        with self.assertRaisesRegex(UserError,'gotowy plik gry'):self.app.mark_ready(ident)

if __name__=='__main__':unittest.main()
