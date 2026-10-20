const {app, BrowserWindow, dialog, ipcMain, shell} = require('electron');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {DesktopUpdater} = require('./updater.cjs');
let backend, win, origin, updater, pendingMod;
app.setName('Recopile Games Hub');
function modArgument(argv) {
  return argv.find(file=>typeof file==='string' && /\.recopilemod$/i.test(file) && fs.existsSync(file) && fs.statSync(file).isFile());
}
function openMod(file) {
  if(!file) return;
  pendingMod=path.resolve(file);
  if(win && !win.isDestroyed() && !win.webContents.isLoading()) win.webContents.send('recopile:mod-package',pendingMod);
}
openMod(modArgument(process.argv));
if (!app.requestSingleInstanceLock()) app.quit();
app.on('second-instance', (_event,argv) => { openMod(modArgument(argv)); if(win) { win.restore(); win.focus(); } });
app.on('open-file',(event,file)=>{event.preventDefault();openMod(modArgument([file]));});

function external(url) {
  try { const u=new URL(url); if(u.protocol==='https:' && !u.username && !u.password) shell.openExternal(u.href); } catch {}
}
function verify(event) { if(!origin || new URL(event.senderFrame.url).origin !== origin) throw new Error('Niedozwolone źródło żądania.'); }
async function startBackend() {
  const packaged=app.isPackaged;
  const executable=packaged ? path.join(process.resourcesPath,'backend','recopile-service'+(process.platform==='win32'?'.exe':'')) : (process.env.RECOPILE_PYTHON || 'python3');
  const cwd=path.resolve(__dirname,'..');
  const data=process.env.RECOPILE_DESKTOP_STATE || app.getPath('userData');
  const argv=[...(packaged?[]:[path.join(cwd,'launcher.py')]),'--no-window','--port','0','--data-dir',data];
  if(process.env.RECOPILE_NO_UPDATES==='1') argv.push('--no-auto-updates');
  backend=spawn(executable,argv,{cwd:packaged?process.resourcesPath:cwd,windowsHide:true,
    env:{...process.env,RECOPILE_NATIVE_DESKTOP:'1',RECOPILE_LIBRARY_ROOT:process.env.RECOPILE_LIBRARY_ROOT || path.join(app.getPath('home'),'Games','RecopileLibrary')},stdio:['ignore','pipe','pipe']});
  return new Promise((resolve,reject) => {
    const timeout=setTimeout(() => reject(new Error('Lokalny serwis nie odpowiedział w ciągu 60 sekund.')),60000);
    let output='', errors='';
    backend.stderr.on('data', data => { errors=(errors+data.toString()).slice(-8000); });
    backend.stdout.on('data', data => {
      output+=data.toString();
      const match=output.match(/Recopile jest uruchomiony: (http:\/\/127\.0\.0\.1:\d+\/)/);
      if(match) { clearTimeout(timeout); origin=new URL(match[1]).origin; resolve(match[1]); }
    });
    backend.once('error', error => { clearTimeout(timeout); reject(error); });
    backend.once('exit', code => { clearTimeout(timeout); if(!origin) reject(new Error(errors || 'Serwis zakończył się z kodem '+code)); else if(win && !app.isQuitting) dialog.showErrorBox('Recopile',errors || 'Lokalny serwis zakończył działanie. Uruchom aplikację ponownie.'); });
  });
}
app.whenReady().then(async () => {
  try {
    const url=await startBackend();
    win=new BrowserWindow({width:1440,height:960,minWidth:840,minHeight:620,title:'RE:COPILE',backgroundColor:'#101114',autoHideMenuBar:true,
      webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true}});
    win.webContents.setWindowOpenHandler(({url}) => { external(url); return {action:'deny'}; });
    win.webContents.on('will-navigate',(event,url) => { if(new URL(url).origin !== origin) { event.preventDefault(); external(url); } });
    win.webContents.session.setPermissionRequestHandler((_contents,_permission,callback) => callback(false));
    await win.loadURL(url);
    updater=new DesktopUpdater(app,origin);
    if(process.env.RECOPILE_NO_UPDATES!=='1') await updater.startup();
    if(process.env.RECOPILE_UI_DEBUG_PORT) win.webContents.openDevTools({mode:'detach'});
  } catch(error) { dialog.showErrorBox('Nie można otworzyć Recopile',error.message); app.quit(); }
});
ipcMain.handle('recopile:pick',async (event,data={}) => { verify(event); const selected=await dialog.showOpenDialog(win,{properties:data.mode==='folder'?['openDirectory']:['openFile']}); return {path:selected.canceled?'':selected.filePaths[0]}; });
ipcMain.handle('recopile:save-image',async (event,data) => {
  verify(event);
  if(typeof data?.base64!=='string' || data.base64.length>10_000_000 || !/^[A-Za-z0-9_.-]{1,180}\.png$/.test(data.filename)) throw new Error('Niepoprawny obraz.');
  const bytes=Buffer.from(data.base64,'base64'); if(!bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('Niepoprawny PNG.');
  const selected=await dialog.showSaveDialog(win,{defaultPath:path.join(app.getPath('pictures'),data.filename),filters:[{name:'PNG',extensions:['png']}]});
  if(!selected.canceled) await fs.promises.writeFile(selected.filePath,bytes); return {saved:!selected.canceled};
});
ipcMain.handle('recopile:restart',event => { verify(event); app.relaunch(); app.quit(); });
ipcMain.handle('recopile:mod-package',event=>{verify(event);const file=pendingMod;pendingMod=null;return file || '';});
ipcMain.handle('recopile:check-launcher',async event => { verify(event); return updater ? updater.check() : {message:'Aktualizator jeszcze się uruchamia.'}; });
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { app.isQuitting=true; if(backend && !backend.killed) backend.kill('SIGINT'); });
