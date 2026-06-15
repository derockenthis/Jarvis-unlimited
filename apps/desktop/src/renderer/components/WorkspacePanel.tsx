import { ChatPane } from './ChatPane';
import { McpToolsView } from './McpToolsView';
import { SettingsView } from './SettingsView';
import { SkillsView } from './SkillsView';
import { useAppStore } from '../stores/useAppStore';

export function WorkspacePanel() {
  const activeWorkspaceView = useAppStore((state) => state.activeWorkspaceView);

  if (activeWorkspaceView === 'settings') {
    return <SettingsView />;
  }

  if (activeWorkspaceView === 'mcp') {
    return <McpToolsView />;
  }

  if (activeWorkspaceView === 'skills') {
    return <SkillsView />;
  }

  return <ChatPane />;
}