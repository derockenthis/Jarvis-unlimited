const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('jarvisDesktop', {
  getAppInfo: () => ipcRenderer.invoke('app:get-info'),
  getBackendUrl: () => ipcRenderer.invoke('backend:get-url'),
  setScreenShareRing: (active) => ipcRenderer.invoke('screen-share:set-ring-active', active),
  getScreenSharingEnabled: () => ipcRenderer.invoke('screen-share:get-enabled'),
  setScreenSharingEnabled: (active) => ipcRenderer.invoke('screen-share:set-enabled', active),
  restoreMainWindowFromMiniChat: () => ipcRenderer.invoke('mini-chat:restore-main-window'),
  getCurrentSessionId: () => ipcRenderer.invoke('session:get-current'),
  setCurrentSessionId: (sessionId) => ipcRenderer.invoke('session:set-current', sessionId),
  getModelSettings: () => ipcRenderer.invoke('settings:get-model'),
  setModelSettings: (settings) => ipcRenderer.invoke('settings:set-model', settings),
  publishChatTurnStarted: (payload) => ipcRenderer.invoke('chat:publish-turn-start', payload),
  publishChatEvent: (payload) => ipcRenderer.invoke('chat:publish-event', payload),
  onChatActivity: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on('chat:activity', listener);
    return () => {
      ipcRenderer.removeListener('chat:activity', listener);
    };
  },
  pickSkillsFolder: () => ipcRenderer.invoke('skills-folder:pick'),
});
