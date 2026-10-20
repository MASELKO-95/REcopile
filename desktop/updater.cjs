const fs=require('node:fs');
const path=require('node:path');
const {autoUpdater}=require('electron-updater');

class DesktopUpdater {
  constructor(app,origin) { this.app=app; this.origin=origin; this.marker=path.join(app.getPath('userData'),'desktop-update.json'); this.checking=false; }
  async api(route,body) {
    const bootstrap=await (await fetch(this.origin+'/api/bootstrap')).json();
    const response=await fetch(this.origin+route,{method:'POST',headers:{'Content-Type':'application/json','X-Recopile-Token':bootstrap.token},body:JSON.stringify(body || {})});
    const result=await response.json(); if(!response.ok) throw new Error(result.error); return result;
  }
  async startup() { return this.check(true); }
  async check(startup=false) {
    if(this.checking) return {message:'Sprawdzanie już trwa.'};
    this.checking=true;
    try {
      const boot=await (await fetch(this.origin+'/api/bootstrap')).json();
      if(!boot.settings.check_updates || !boot.settings.launcher_repo) return {message:'Repozytorium nie jest skonfigurowane lub sprawdzanie jest wyłączone.'};
      const available=await this.api('/api/check-launcher');
      if(!available.available || !this.app.isPackaged) return available;
      if(process.platform==='linux' && !process.env.APPIMAGE) return {...available,message:'Automatyczna aktualizacja Linux jest dostępna w wydaniu AppImage. Dla DEB pobierz nowy pakiet.'};
      const [owner,repo]=boot.settings.launcher_repo.split('/');
      autoUpdater.autoDownload=false; autoUpdater.autoInstallOnAppQuit=false; autoUpdater.allowPrerelease=false; autoUpdater.allowDowngrade=false;
      autoUpdater.setFeedURL({provider:'github',owner,repo,private:false});
      let previous={}; try { previous=JSON.parse(fs.readFileSync(this.marker,'utf8')); } catch {}
      const checked=await autoUpdater.checkForUpdates();
      if(!checked || !checked.updateInfo) return available;
      const version=checked.updateInfo.version;
      if(version!==available.version.replace(/^v/,'')) throw new Error('Niezgodna wersja metadanych aktualizacji.');
      const temp=this.marker+'.tmp'; fs.writeFileSync(temp,JSON.stringify({version})); fs.renameSync(temp,this.marker);
      const permission=await this.api('/api/launcher-permission');
      if(startup && previous.version===version && permission.permitted && permission.auto && boot.settings.onboarding_complete) {
        autoUpdater.on('download-progress',progress => this.api('/api/launcher-progress',{progress:progress.percent,message:'Pobieranie nowej wersji launchera'}).catch(() => {}));
        await autoUpdater.downloadUpdate();
        await this.api('/api/launcher-progress',{progress:100,message:'Ponowne uruchomienie z nową wersją'});
        this.app.isQuitting=true;
        autoUpdater.quitAndInstall(true,true);
      }
      return available;
    } catch(error) {
      await this.api('/api/launcher-progress',{message:'Sprawdzenie launchera: '+error.message}).catch(() => {});
      return {error:error.message};
    } finally { this.checking=false; }
  }
}
module.exports={DesktopUpdater};
