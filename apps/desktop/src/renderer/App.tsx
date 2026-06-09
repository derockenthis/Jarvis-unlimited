import { useEffect } from 'react';
import { ChatPane } from './components/ChatPane';
import { LiveWindow } from './components/LiveWindow';
import { Sidebar } from './components/Sidebar';
import { useAppStore } from './stores/useAppStore';

export function App() {
  const setBackendUrl = useAppStore((state) => state.setBackendUrl);
  const isScreenSharing = useAppStore((state) => state.isScreenSharing);
  const isScreenViewing = useAppStore((state) => state.isScreenViewing);

  useEffect(() => {
    window.jarvisDesktop?.getBackendUrl().then(setBackendUrl).catch(() => undefined);
  }, [setBackendUrl]);

  useEffect(() => {
    const active = isScreenSharing || isScreenViewing;
    window.jarvisDesktop?.setScreenShareRing(active).catch(() => undefined);
  }, [isScreenSharing, isScreenViewing]);

  return (
    <main className="app-shell">
      <Sidebar />
      <ChatPane />
      <LiveWindow />
    </main>
  );
}
