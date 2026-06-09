/// <reference types="vite/client" />

type JarvisAppInfo = {
  name: string;
  version: string;
  backendUrl: string;
  isPackaged: boolean;
};

interface Window {
  jarvisDesktop?: {
    getAppInfo: () => Promise<JarvisAppInfo>;
    getBackendUrl: () => Promise<string>;
    setScreenShareRing: (active: boolean) => Promise<{ active: boolean }>;
    pickSkillsFolder: () => Promise<string | null>;
  };
}
