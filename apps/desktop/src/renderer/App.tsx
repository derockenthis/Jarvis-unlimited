import { useEffect } from 'react';
import { LiveWindow } from './components/LiveWindow';
import { MiniChat } from './components/MiniChat';
import { Sidebar } from './components/Sidebar';
import { WorkspacePanel } from './components/WorkspacePanel';
import { useAppStore } from './stores/useAppStore';
import type { ChatEvent } from './types';

export function App() {
  const isMiniChat = new URLSearchParams(window.location.search).get('miniChat') === '1';
  const setBackendUrl = useAppStore((state) => state.setBackendUrl);
  const loadProviderSettings = useAppStore((state) => state.loadProviderSettings);
  const isScreenSharing = useAppStore((state) => state.isScreenSharing);
  const isScreenViewing = useAppStore((state) => state.isScreenViewing);
  const sessionId = useAppStore((state) => state.sessionId);
  const setSessionId = useAppStore((state) => state.setSessionId);
  const setActiveWorkspaceView = useAppStore((state) => state.setActiveWorkspaceView);
  const setStreaming = useAppStore((state) => state.setStreaming);
  const addUserMessage = useAppStore((state) => state.addUserMessage);
  const addChatEvent = useAppStore((state) => state.addChatEvent);

  useEffect(() => {
    let cancelled = false;

    window.jarvisDesktop?.getBackendUrl().then((backendUrl) => {
      if (cancelled) {
        return;
      }
      setBackendUrl(backendUrl);
      void loadProviderSettings(true);
    }).catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [loadProviderSettings, setBackendUrl]);

  useEffect(() => {
    if (isMiniChat) {
      return;
    }
    window.jarvisDesktop?.setCurrentSessionId(sessionId).catch(() => undefined);
  }, [isMiniChat, sessionId]);

  useEffect(() => {
    if (isMiniChat) {
      return;
    }

    const unsubscribe = window.jarvisDesktop?.onChatActivity?.((payload) => {
      if (payload.type === 'turn_started') {
        setSessionId(payload.session_id);
        setActiveWorkspaceView('chat');
        setStreaming(true);
        addUserMessage(payload.content);
        return;
      }

      addChatEvent(payload.event as ChatEvent);
      if (payload.event.type === 'done' || payload.event.type === 'error') {
        setStreaming(false);
      }
    });

    return () => {
      unsubscribe?.();
    };
  }, [addChatEvent, isMiniChat, setActiveWorkspaceView, setSessionId, setStreaming, addUserMessage]);

  useEffect(() => {
    const active = isScreenSharing || isScreenViewing;
    window.jarvisDesktop?.setScreenShareRing(active).catch(() => undefined);
  }, [isScreenSharing, isScreenViewing]);

  if (isMiniChat) {
    return <MiniChat />;
  }

  return (
    <main className="app-shell">
      <Sidebar />
      <WorkspacePanel />
      <LiveWindow />
    </main>
  );
}
