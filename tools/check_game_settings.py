#!/usr/bin/env python3
"""Exercise the real upstream CLI in disposable profiles, without game data.

GPL-3.0-only. Copyright (C) 2026 MASELKO-95. Added 2026-10-20.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from recopile.service import Launcher
from recopile.storage import game_id
from recopile.network import UserError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pinyon-source',type=Path,required=True)
    parser.add_argument('--legacy-source',type=Path)
    args=parser.parse_args()
    report={}
    with tempfile.TemporaryDirectory(prefix='recopile-real-settings-') as temp:
        root=Path(temp)
        app=Launcher(ROOT,root/'hub',automatic=False)
        try:
            ident=game_id('xbox360','Forza Horizon')
            app.save_preferences({'games_dir':str(root/'library')})
            paths=app.game_location(ident,'Forza Horizon','xbox360')
            for name,source in [('pinyon',args.pinyon_source),('pinyon-linux',args.legacy_source)]:
                if source is None:continue
                state=root/name
                save=state/'user/ForzaProfile/ForzaProfile'
                save.parent.mkdir(parents=True);save.write_bytes(b'preserved existing save fixture')
                app.save_install(ident,{'id':ident,**paths,'source_id':name,'engine_root':str(source.resolve(strict=True)),'pinyon_state_root':str(state),'ready':False})
                def request(operation='get',**data):return app.game_settings.request(ident,{'operation':operation,**data})
                original=request()
                assert not (state/'config/pinyon_shift.toml').exists(), 'Reading defaults must not write a configuration file'
                assert not app.running, 'Settings must not launch the game'
                if name=='pinyon':
                    for scaling in ('fsr2','fsr3','dlss'):
                        result=request('apply',values={'output_scaling':scaling,'resolution_scale':2,'render_fps':40,'disable_motion_blur':False})
                        assert result['settings']['output_scaling']==scaling,result
                        assert result['settings']['render_fps']==40,result
                    assert len(list((state/'config/backups').glob('*.toml')))>=2
                    result=request('reset')
                    assert result['settings']['output_scaling']=='bilinear'
                    result=request('restore')
                    assert result['settings']['output_scaling']=='dlss',result
                    report[name]={'driver':original['driver'],'fsr2_fsr3_dlss_persist':True,'reset_restore':True,'backup_files':len(list((state/'config/backups').glob('*.toml')))}
                else:
                    result=request('apply',values={'output_scaling':'fsr','controls':'pc-steering','render_fps':40})
                    assert result['settings']['output_scaling']=='fsr'
                    assert result['settings']['controls']=='pc-steering'
                    try:request('apply',values={'output_scaling':'fsr2'})
                    except UserError:pass
                    else:raise AssertionError('Old Linux patch cannot offer FSR 2')
                    report[name]={'driver':original['driver'],'legacy_patch':True,'unsupported_fsr2_rejected':True}
                before=(state/'config/pinyon_shift.toml').read_bytes()
                try:request('apply',values={'resolution_scale':999},launch={'arguments':[]})
                except UserError:pass
                else:raise AssertionError('Invalid setting accepted')
                assert (state/'config/pinyon_shift.toml').read_bytes()==before
                assert save.read_bytes()==b'preserved existing save fixture'
                assert not app.running
                report[name]['save_unchanged']=True
        finally:
            app.shutdown();app.jobs.pool.shutdown(wait=True);app.media.pool.shutdown(wait=True)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
