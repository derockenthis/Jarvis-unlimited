const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('jarvisDesktop', {
  getAppInfo: () => ipcRenderer.invoke('app:get-info'),
  getBackendUrl: () => ipcRenderer.invoke('backend:get-url'),
  setScreenShareRing: (active) => ipcRenderer.invoke('screen-share:set-ring-active', active),
  pickSkillsFolder: () => ipcRenderer.invoke('skills-folder:pick'),
});
