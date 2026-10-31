"""On-demand community packages use real assets and the existing consent flow."""
import json
import base64
import hashlib
import io
import tempfile
import time
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from recopile.catalog_lists import reference_source
from recopile.community_packages import find_entrypoint, resolve
from recopile.network import UserError
from recopile.service import Launcher
from recopile.storage import Store, game_id

ROOT=Path(__file__).resolve().parents[1]
def asset(name):
    return {'name':name,'size':100,'browser_download_url':'https://github.com/example/new-port/releases/download/v1/'+name}


class CommunityPackageTests(unittest.TestCase):
    def setUp(self):
        self.source=reference_source({'title':'New Test Game','repo':'example/new-port'})

    def test_native_package_preferred_over_android_sources_and_compatibility_bundles(self):
        releases=[{'tag_name':'v1','assets':[asset(name) for name in ('Game.apk','Game-linux-source.zip','Game-windows-x64.zip','Game-x86_64.AppImage','Game-linux.zip')]}]
        with patch('recopile.community_packages.fetch_json',return_value=releases):
            source=resolve(self.source,'linux')
        self.assertEqual(source['assets_by_system'],{'linux':'Game-x86_64.AppImage'})
        self.assertNotIn('origin',source);self.assertTrue(source['auto_executable'])
        self.assertFalse(source['auto_update']);self.assertFalse(source['verified'])

    def test_ambiguous_archives_require_explicit_package_selection(self):
        with patch('recopile.community_packages.fetch_json',return_value=[{'assets':[asset('Game-linux-a.zip'),asset('Game-linux-b.zip')]}]):
            with self.assertRaisesRegex(UserError,'kilka paczek'):resolve(self.source,'linux')

    def test_windows_installers_and_linux_are_distinct(self):
        with patch('recopile.community_packages.fetch_json',return_value=[{'assets':[asset('GameSetup.exe')]}]):
            source=resolve(self.source,'windows')
            self.assertEqual(source['adapter'],'installer')
            self.assertNotIn('linux',source['assets_by_system'])
            with self.assertRaises(UserError):resolve(self.source,'linux')

    def test_entrypoint_does_not_select_libraries_build_scripts_or_an_arbitrary_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'game').write_bytes(b'\x7fELFfixture')
            (root/'library.so').write_bytes(b'\x7fELFfixture')
            (root/'build.sh').write_text('#!/bin/sh\nexit 0\n')
            self.assertEqual(find_entrypoint(root,'linux'),root/'game')
            (root/'another-game').write_bytes(b'\x7fELFfixture')
            with self.assertRaises(UserError):find_entrypoint(root,'linux')

    def test_windows_entrypoint_uses_the_unique_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('game.exe','GameLauncher.exe','vcredist.exe'):(root/name).write_bytes(b'MZfixture')
            self.assertEqual(find_entrypoint(root,'windows').name,'GameLauncher.exe')

    def test_game_titles_are_not_mistaken_for_crash_reporters_or_test_utilities(self):
        for name in ('CrashRecomp.exe','TestDriveUnlimited.exe'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                for helper in (name,'crashpad_handler.exe','crashreporter.exe','unit-test.exe'):
                    (root/helper).write_bytes(b'MZfixture')
                self.assertEqual(find_entrypoint(root,'windows').name,name)

    def test_arm_linux_packages_are_not_selected_for_x86_64(self):
        releases=[{'assets':[asset('Game-linux-armv7.tar.gz'),asset('Game-linux-aarch64.zip')]}]
        with patch('recopile.community_packages.fetch_json',return_value=releases):
            with self.assertRaises(UserError):resolve(self.source,'linux')

    def test_cached_os_packages_keep_their_own_adapter_and_entrypoint(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Launcher(ROOT,Path(folder),automatic=False,scan_steam=False)
            try:
                source={**self.source,'package_resolved':True,'origin':None,'resolved_system':'windows',
                        'adapter':'installer','assets_by_system':{'windows':'GameSetup.exe','linux':'Game-linux.zip'},
                        'executables_by_system':{'windows':'GameSetup.exe','linux':''}}
                source.pop('origin')
                for system,adapter in [('linux','native'),('windows','installer')]:
                    with self.subTest(system=system),patch.object(app,'system_key',return_value=system):
                        target=app.target_source(source)
                    self.assertEqual(target['resolved_system'],system)
                    self.assertEqual(target['adapter'],adapter)
                    self.assertTrue(target['auto_executable'])
            finally:
                app.shutdown();app.jobs.pool.shutdown(wait=True);app.media.pool.shutdown(wait=True)

    def test_download_review_and_extraction_preserve_unprepared_state_for_archives_and_installers(self):
        for system,package_system in (('linux','linux'),('windows','windows'),('linux','windows')):
            with self.subTest(system=system,package_system=package_system),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                app=Launcher(ROOT,root/'state',automatic=False,scan_steam=False)
                try:
                    app.save_preferences({'games_dir':str(root/'library')})
                    app.store.put('sources',self.source['id'],self.source)
                    ident=game_id('xbox360','New Test Game')
                    app.store.save_game({'id':ident,'title':'New Test Game','platform':'xbox360','kind':'recompile','source_ids':[self.source['id']],'variants':[]})
                    if package_system=='linux' or system=='linux':
                        archive=io.BytesIO()
                        with zipfile.ZipFile(archive,'w') as bundle:bundle.writestr('CrashRecomp' if package_system=='linux' else 'GameLauncher.exe',b'\x7fELFsynthetic fixture, never executed' if package_system=='linux' else b'MZsynthetic fixture, never executed')
                        raw=archive.getvalue();name='Game-linux.zip' if package_system=='linux' else 'Game-windows-x64.zip'
                    else:raw=b'MZsynthetic installer fixture, never executed';name='GameSetup.exe'
                    digest=hashlib.sha256(raw).hexdigest()
                    package={**asset(name),'size':len(raw),'digest':'sha256:'+digest}
                    metadata={'version':'v1','url':'https://github.com/example/new-port/releases/tag/v1','asset':package,'assets':[package]}
                    def document(text):return {'available':True,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()}
                    documents={'repo':self.source['repo'],'version':'v1','name':'Fixture','fingerprint':'f'*64,
                               'readme':document('Synthetic fixture instructions'),'license':document('Synthetic fixture license')}
                    def download(_asset,path,progress,cancelled,checksum):
                        self.assertEqual(checksum,digest);path.write_bytes(raw);progress(len(raw),len(raw));return digest
                    release={'tag_name':'v1','assets':[package]}
                    with patch.object(app,'system_key',return_value=system),patch('recopile.community_packages.fetch_json',return_value=[release]),patch.object(app,'release',return_value=metadata),patch.object(app.documents,'get',return_value=documents),patch('recopile.service.download',side_effect=download) as fetch,patch('recopile.service.subprocess.Popen') as execute,patch('recopile.service.runners.discover',return_value={'proton':[],'wine':'/fixture/wine'}):
                        review=app.install(self.source['id'],ident)
                        self.assertTrue(review['review_required']);fetch.assert_not_called()
                        with self.assertRaises(UserError):app.install(self.source['id'],ident,review=documents['fingerprint'],license_accepted=False)
                        fetch.assert_not_called()
                        job=app.install(self.source['id'],ident,review=documents['fingerprint'],license_accepted=True,license_hash=documents['license']['sha256'])
                        deadline=time.monotonic()+8
                        while time.monotonic()<deadline:
                            saved=app.store.get('jobs',job['id'])
                            if saved['status'] not in ('queued','running'):break
                            time.sleep(.02)
                        self.assertEqual(saved['status'],'completed',saved)
                        execute.assert_not_called()
                    installed=app.store.get('installs',ident)
                    self.assertFalse(installed['ready'])
                    self.assertEqual(installed['package_system'],package_system)
                    if system=='linux' and package_system=='windows':self.assertEqual(installed['runner'],'wine')
                    self.assertTrue(saved['result']['requires_setup'])
                    self.assertEqual((Path(installed['runtime_dir'])/'Recopile-project-info/LICENSE').read_text(),documents['license']['text'])
                    self.assertEqual(Path(installed['executable']).read_bytes(),raw if system=='windows' else b'\x7fELFsynthetic fixture, never executed' if package_system=='linux' else b'MZsynthetic fixture, never executed')
                finally:
                    app.shutdown();app.jobs.pool.shutdown(wait=True);app.media.pool.shutdown(wait=True)

    def test_resolved_source_survives_offline_restart_and_download_still_requires_documents(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            app=Launcher(ROOT,root/'state',automatic=False,scan_steam=False)
            try:
                app.save_preferences({'games_dir':str(root/'library')})
                original=next(s for s in app.store.list('sources') if s.get('development_status')=='listed')
                with app.store.connect() as db:
                    games=[json.loads(row[0]) for row in db.execute("SELECT payload FROM games WHERE kind='recompile'")]
                game=next(g for g in games if original['id'] in g.get('source_ids',[]))
                resolved={**original,'trusted':True,'asset_pattern':'Game-linux.zip','assets_by_system':{'linux':'Game-linux.zip'},
                          'auto_executable':True,'package_resolved':True}
                resolved.pop('origin');resolved.pop('development_status')
                with patch('recopile.community_packages.resolve',return_value=resolved),patch.object(app,'release',return_value={}),patch.object(app.documents,'get',return_value={'fingerprint':'fixture'}),patch.object(app.documents,'permitted',return_value=False),patch('recopile.service.download') as download:
                    result=app.install(original['id'],game['id'])
                self.assertTrue(result['review_required']);download.assert_not_called()
                restarted=Store(ROOT,app.store.root)
                self.assertEqual(restarted.get('sources',original['id'])['assets_by_system'],resolved['assets_by_system'])
                self.assertNotIn('origin',restarted.get('sources',original['id']))
            finally:
                app.shutdown();app.jobs.pool.shutdown(wait=True);app.media.pool.shutdown(wait=True)

    def test_windows_setup_on_linux_uses_saved_runner_without_recording_gameplay(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            app=Launcher(ROOT,root/'state',automatic=False,scan_steam=False)
            try:
                app.save_preferences({'games_dir':str(root/'library')})
                ident=game_id('xbox360','New Test Game')
                app.store.save_game({'id':ident,'title':'New Test Game','platform':'xbox360','kind':'recompile','source_ids':[],'variants':[]})
                paths=app.game_location(ident,'New Test Game','xbox360')
                runtime=Path(paths['game_root'])/'versions/fixture'
                exe=runtime/'nested/GameLauncher.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'MZnever executed');exe.chmod(0o755)
                installed={'id':ident,**paths,'runtime_dir':str(runtime),
                           'executable':str(exe),'package_system':'windows','adapter':'native','ready':False}
                app.store.put('installs',ident,installed)
                with patch.object(app,'system_key',return_value='linux'):
                    settings=app.game_settings.request(ident,{'operation':'get'})
                    self.assertTrue(settings['can_compatibility'])
                    self.assertFalse(app.game_settings.can_compatibility({**installed,'local_executable':'/local/native-game','local_system':'linux'}))
                    app.game_settings.request(ident,{'operation':'apply','launch':{'arguments':[],'runner':'wine','proton_path':''}})
                    process=Mock(pid=12345);process.wait.return_value=0
                    with patch('recopile.service.runners.command',return_value=([sys.executable,'-c','pass'],{})) as wrapper,patch('recopile.service.subprocess.Popen',return_value=process) as launch,patch.object(app.profiles,'record') as recorded:
                        result=app.launch(ident,setup=True)
                        deadline=time.monotonic()+2
                        while ident in app.running and time.monotonic()<deadline:time.sleep(.01)
                        self.assertTrue(result['ok']);self.assertNotIn(ident,app.running)
                        request=wrapper.call_args.args[0]
                        self.assertEqual(request['local_executable'],str(exe));self.assertEqual(request['runner'],'wine')
                        self.assertEqual(launch.call_args.kwargs['cwd'],exe.parent)
                        recorded.assert_not_called()
                    self.assertFalse(app.store.get('installs',ident)['ready'])
                    with self.assertRaises(UserError):app.launch(ident)
            finally:
                app.shutdown();app.jobs.pool.shutdown(wait=True);app.media.pool.shutdown(wait=True)

    def test_reviewed_catalog_adapter_replaces_discovery_without_losing_the_game_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Launcher(ROOT,Path(folder),automatic=False,scan_steam=False)
            try:
                app.save_preferences({'launcher_repo':'example/catalog'})
                registry=json.loads((ROOT/'data/registry.json').read_text())
                reference=next(s for s in registry['sources'] if s.get('development_status')=='listed')
                game=next(g for g in registry['featured'] if reference['id'] in g.get('source_ids',[]))
                ident=game_id(game['platform'],game['match'])
                resolved={**reference,'package_resolved':True,'resolved_system':'linux','auto_executable':True,'trusted':True}
                resolved.pop('origin');resolved.pop('development_status');app.store.put('sources',reference['id'],resolved)
                curated={**reference,'asset_pattern':'Game-linux.zip','assets_by_system':{'linux':'Game-linux.zip'},
                         'executable':'game','executables_by_system':{'linux':'game'},'adapter':'native-wizard','verified':True}
                for key in ('origin','development_status','discover_packages'):curated.pop(key,None)
                payload={'schema_version':1,'sources':[curated],'featured':[game],'catalog_version':'2099-01-01.1'}
                response={'encoding':'base64','content':base64.b64encode(json.dumps(payload).encode()).decode()}
                with patch('recopile.service.fetch_json',return_value=response):app.sync_catalog()
                updated=app.source(reference['id'])
                self.assertEqual(updated['adapter'],'native-wizard');self.assertNotIn('package_resolved',updated)
                self.assertFalse(updated.get('discover_packages'))
                with patch.object(app,'system_key',return_value='linux'):self.assertEqual(app.target_source(updated)['adapter'],'native-wizard')
                self.assertIn(reference['id'],app.store.game(ident)['source_ids'])
            finally:
                app.shutdown();app.jobs.pool.shutdown(wait=True);app.media.pool.shutdown(wait=True)

if __name__=='__main__':unittest.main()
