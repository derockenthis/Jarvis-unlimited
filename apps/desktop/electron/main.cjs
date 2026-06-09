const { app, BrowserWindow, dialog, ipcMain, screen, shell, session } = require('electron');
const path = require('node:path');

const isDev = !app.isPackaged;
const rendererUrl = process.env.JARVIS_RENDERER_URL || 'http://127.0.0.1:5173';
const backendUrl = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8765';
const screenShareOverlays = new Map();
let screenShareRingActive = false;

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

  return window;
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
  createMainWindow();

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
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on('window-all-closed', () => {
  setScreenShareRing(false);
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
