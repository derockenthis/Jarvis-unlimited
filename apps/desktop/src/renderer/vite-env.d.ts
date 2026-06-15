/// <reference types="vite/client" />

type JarvisAppInfo = {
  name: string;
  version: string;
  backendUrl: string;
  isPackaged: boolean;
};

type JarvisModelSettings = {
  provider: string;
  model: string;
  apiKey: string;
  baseUrl: string;
  speechModel: string;
};

interface Window {
  jarvisDesktop?: {
    getAppInfo: () => Promise<JarvisAppInfo>;
    getBackendUrl: () => Promise<string>;
    setScreenShareRing: (active: boolean) => Promise<{ active: boolean }>;
    getScreenSharingEnabled: () => Promise<{ active: boolean }>;
    setScreenSharingEnabled: (active: boolean) => Promise<{ active: boolean }>;
    restoreMainWindowFromMiniChat: () => Promise<{ restored: boolean }>;
    getCurrentSessionId: () => Promise<{ session_id: string | null }>;
    setCurrentSessionId: (sessionId: string) => Promise<{ session_id: string | null }>;
    getModelSettings: () => Promise<{ settings: JarvisModelSettings | null }>;
    setModelSettings: (settings: JarvisModelSettings) => Promise<{ settings: JarvisModelSettings | null }>;
    publishChatTurnStarted: (payload: { session_id: string; content: string }) => Promise<{ status: string }>;
    publishChatEvent: (payload: { session_id: string; event: { type: string; content: string; payload?: { tool_name?: string | null; status?: string | null; detail?: string | null } } }) => Promise<{ status: string }>;
    onChatActivity: (callback: (payload: { type: 'turn_started'; session_id: string; content: string } | { type: 'event'; session_id: string; event: { type: string; content: string; payload?: { tool_name?: string | null; status?: string | null; detail?: string | null } } }) => void) => () => void;
    pickSkillsFolder: () => Promise<string | null>;
  };
}
