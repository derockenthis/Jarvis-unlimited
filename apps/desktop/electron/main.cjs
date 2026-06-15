const { app, BrowserWindow, dialog, ipcMain, screen, shell, session } = require('electron');
const path = require('node:path');

const isDev = !app.isPackaged;
const rendererUrl = process.env.JARVIS_RENDERER_URL || 'http://127.0.0.1:5173';
const backendUrl = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8765';
const screenShareOverlays = new Map();
let screenShareRingActive = false;
let screenSharingEnabled = false;
let mainWindow = null;
let miniChatWindow = null;
let sharedSessionId = null;
let sharedModelSettings = null;

function createScreenShareOverlay(display) {
  const overlay = new BrowserWindow({
    x: display.bounds.x,
    y: display.bounds.y,
    width: display.bounds.width,
    height: display.bounds.height,
    frame: false,
    transparent: true,
    resizable: false,
    movable: false,
    fullscreenable: false,
    focusable: false,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    alwaysOnTop: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  overlay.setIgnoreMouseEvents(true, { forward: true });
  overlay.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  overlay.setAlwaysOnTop(true, 'screen-saver');
  overlay.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`
    <!doctype html>
    <html>
      <head>
        <style>
          html, body { width: 100%; height: 100%; margin: 0; background: transparent; overflow: hidden; }
          .ring {
            position: fixed;
            inset: 10px;
            border: 8px solid hsl(202 86% 55%);
            border-radius: 28px;
            box-shadow: 0 0 28px hsl(202 86% 55% / 0.72), inset 0 0 24px hsl(42 92% 58% / 0.38);
            animation: color-cycle 3.6s linear infinite, pulse 1.6s ease-in-out infinite;
          }
          @keyframes color-cycle {
            0% { filter: hue-rotate(0deg); }
            100% { filter: hue-rotate(360deg); }
          }
          @keyframes pulse {
            0%, 100% { opacity: 0.72; transform: scale(0.997); }
            50% { opacity: 1; transform: scale(1); }
          }
        </style>
      </head>
      <body><div class="ring"></div></body>
    </html>
  `)}`);
  overlay.on('closed', () => {
    screenShareOverlays.delete(display.id);
  });
  return overlay;
}

function syncScreenShareOverlays() {
  const activeDisplayIds = new Set(screen.getAllDisplays().map((display) => display.id));

  for (const [displayId, overlay] of screenShareOverlays.entries()) {
    if (!activeDisplayIds.has(displayId) && !overlay.isDestroyed()) {
      overlay.close();
    }
  }

  for (const display of screen.getAllDisplays()) {
    const existing = screenShareOverlays.get(display.id);
    if (existing && !existing.isDestroyed()) {
      existing.setBounds(display.bounds);
      existing.showInactive();
      continue;
    }

    const overlay = createScreenShareOverlay(display);
    screenShareOverlays.set(display.id, overlay);
    overlay.showInactive();
  }
}

function setScreenShareRing(active) {
  screenShareRingActive = active;
  if (!active) {
    for (const overlay of screenShareOverlays.values()) {
      if (!overlay.isDestroyed()) {
        overlay.close();
      }
    }
    screenShareOverlays.clear();
    return { active: false };
  }

  syncScreenShareOverlays();
  return { active: true };
}

function setScreenSharingEnabled(active) {
  screenSharingEnabled = Boolean(active);
  return { active: screenSharingEnabled };
}

function getScreenSharingEnabled() {
  return { active: screenSharingEnabled };
}

function createMainWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1080,
    minHeight: 720,
    title: 'Jarvis Agent Desktop',
    backgroundColor: '#f5f3ee',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 18, y: 18 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (isDev) {
    window.loadURL(rendererUrl);
  } else {
    window.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  window.on('minimize', () => {
    showMiniChatWindow();
  });

  window.on('restore', () => {
    hideMiniChatWindow();
  });

  window.on('focus', () => {
    if (!window.isMinimized()) {
      hideMiniChatWindow();
    }
  });

  window.on('closed', () => {
    if (mainWindow === window) {
      mainWindow = null;
    }
    closeMiniChatWindow();
  });

  mainWindow = window;
  return window;
}

function createMiniChatWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const width = 620;
  const height = 74;
  const x = Math.round(primaryDisplay.workArea.x + (primaryDisplay.workArea.width - width) / 2);
  const y = Math.round(primaryDisplay.workArea.y + primaryDisplay.workArea.height - height - 26);
  const window = new BrowserWindow({
    x,
    y,
    width,
    height,
    minWidth: 420,
    minHeight: 64,
    maxHeight: 120,
    frame: false,
    transparent: true,
    resizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    alwaysOnTop: true,
    title: 'Jarvis Mini Chat',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  window.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  window.setAlwaysOnTop(true, 'floating');

  if (isDev) {
    window.loadURL(`${rendererUrl}?miniChat=1`);
  } else {
    window.loadFile(path.join(__dirname, '../dist/index.html'), { query: { miniChat: '1' } });
  }

  window.on('closed', () => {
    if (miniChatWindow === window) {
      miniChatWindow = null;
    }
  });

  return window;
}

function showMiniChatWindow() {
  if (!miniChatWindow || miniChatWindow.isDestroyed()) {
    miniChatWindow = createMiniChatWindow();
  }

  miniChatWindow.showInactive();
}

function hideMiniChatWindow() {
  if (miniChatWindow && !miniChatWindow.isDestroyed()) {
    miniChatWindow.hide();
  }
}

function closeMiniChatWindow() {
  if (miniChatWindow && !miniChatWindow.isDestroyed()) {
    miniChatWindow.close();
  }
  miniChatWindow = null;
}

function restoreMainWindowFromMiniChat() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = createMainWindow();
  }

  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  mainWindow.show();
  mainWindow.focus();
  hideMiniChatWindow();
  return { restored: true };
}

function setSharedSessionId(sessionId) {
  sharedSessionId = typeof sessionId === 'string' && sessionId.trim() ? sessionId : null;
  return { session_id: sharedSessionId };
}

function getSharedSessionId() {
  return { session_id: sharedSessionId };
}

function setSharedModelSettings(settings) {
  sharedModelSettings = settings && typeof settings === 'object' ? { ...settings } : null;
  return { settings: sharedModelSettings };
}

function getSharedModelSettings() {
  return { settings: sharedModelSettings };
}

function broadcastChatActivity(payload) {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed()) {
      window.webContents.send('chat:activity', payload);
    }
  }
}

function isTrustedRendererOrigin(origin) {
  if (isDev) {
    return origin === rendererUrl || origin.startsWith(`${rendererUrl}/`);
  }
  return origin.startsWith('file://');
}

function configurePermissions() {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const origin = webContents.getURL();
    callback(permission === 'media' && isTrustedRendererOrigin(origin));
  });

  session.defaultSession.setPermissionCheckHandler((_webContents, permission, requestingOrigin) => (
    permission === 'media' && isTrustedRendererOrigin(requestingOrigin)
  ));
}

ipcMain.handle('app:get-info', () => ({
  name: app.getName(),
  version: app.getVersion(),
  backendUrl,
  isPackaged: app.isPackaged,
}));

ipcMain.handle('backend:get-url', () => backendUrl);
ipcMain.handle('screen-share:set-ring-active', (_event, active) => setScreenShareRing(Boolean(active)));
ipcMain.handle('screen-share:get-enabled', () => getScreenSharingEnabled());
ipcMain.handle('screen-share:set-enabled', (_event, active) => setScreenSharingEnabled(Boolean(active)));
ipcMain.handle('mini-chat:restore-main-window', () => restoreMainWindowFromMiniChat());
ipcMain.handle('session:get-current', () => getSharedSessionId());
ipcMain.handle('session:set-current', (_event, sessionId) => setSharedSessionId(String(sessionId || '')));
ipcMain.handle('settings:get-model', () => getSharedModelSettings());
ipcMain.handle('settings:set-model', (_event, settings) => setSharedModelSettings(settings));
ipcMain.handle('chat:publish-turn-start', (_event, payload) => {
  broadcastChatActivity({ type: 'turn_started', ...payload });
  return { status: 'ok' };
});
ipcMain.handle('chat:publish-event', (_event, payload) => {
  broadcastChatActivity({ type: 'event', ...payload });
  return { status: 'ok' };
});
ipcMain.handle('skills-folder:pick', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select skills folder',
  });

  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }

  return result.filePaths[0];
});

app.whenReady().then(() => {
  configurePermissions();
  mainWindow = createMainWindow();

  screen.on('display-added', () => {
    if (screenShareRingActive) {
      syncScreenShareOverlays();
    }
  });
  screen.on('display-removed', () => {
    if (screenShareRingActive) {
      syncScreenShareOverlays();
    }
  });
  screen.on('display-metrics-changed', () => {
    if (screenShareRingActive) {
      syncScreenShareOverlays();
    }
  });

  app.on('activate', () => {
    if (!mainWindow || mainWindow.isDestroyed()) {
      mainWindow = createMainWindow();
    }
  });
});

app.on('window-all-closed', () => {
  setScreenShareRing(false);
  closeMiniChatWindow();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
