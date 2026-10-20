const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('recopile', {
  pickPath: data => ipcRenderer.invoke('recopile:pick', data),
  saveImage: data => ipcRenderer.invoke('recopile:save-image', data),
  restart: () => ipcRenderer.invoke('recopile:restart'),
  checkLauncher: () => ipcRenderer.invoke('recopile:check-launcher'),
  getModPackage: () => ipcRenderer.invoke('recopile:mod-package'),
  onModPackage: callback => {
    const handler=(_event,file)=>{if(typeof file==='string')callback(file);};
    ipcRenderer.on('recopile:mod-package',handler);
    return ()=>ipcRenderer.removeListener('recopile:mod-package',handler);
  },
});
