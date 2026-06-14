import { ChevronLeft, ChevronRight, Cpu, FolderOpen, MessageSquare, Wrench } from 'lucide-react';
import { useAppStore } from '../stores/useAppStore';
import type { ChatMessage, WorkspaceView } from '../types';

type NavItem = {
  view: WorkspaceView;
  label: string;
  icon: typeof Cpu;
};

const navItems: NavItem[] = [
  { view: 'provider', label: 'Provider', icon: Cpu },
  { view: 'mcp', label: 'MCP Tools', icon: Wrench },
  { view: 'skills', label: 'Skills', icon: FolderOpen },
];

function getRecentUserMessages(messages: ChatMessage[]) {
  return messages.filter((message) => message.role === 'user').slice(-5).reverse();
}

function getRecentLabel(message: ChatMessage) {
  const firstLine = message.content.replace(/\s+/g, ' ').trim();
  if (!firstLine) {
    return 'Untitled chat';
  }
  return firstLine.length > 44 ? `${firstLine.slice(0, 44)}...` : firstLine;
}

export function Sidebar() {
  const collapsed = useAppStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const activeWorkspaceView = useAppStore((state) => state.activeWorkspaceView);
  const setActiveWorkspaceView = useAppStore((state) => state.setActiveWorkspaceView);
  const messages = useAppStore((state) => state.messages);
  const recents = getRecentUserMessages(messages);

  return (
    <aside className={collapsed ? 'sidebar sidebar-collapsed' : 'sidebar'}>
      <div className="sidebar-topline" />
      <div className="sidebar-header">
        {!collapsed ? (
          <div>
            <p className="eyebrow">Workspace</p>
            <h1>Jarvis</h1>
          </div>
        ) : null}
        <button className="icon-button" type="button" onClick={toggleSidebar} aria-label="Toggle sidebar">
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <nav className="sidebar-nav" aria-label="Workspace views">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activeWorkspaceView === item.view;
          return (
            <button
              className={active ? 'sidebar-nav-item sidebar-nav-item-active' : 'sidebar-nav-item'}
              type="button"
              key={item.view}
              onClick={() => setActiveWorkspaceView(item.view)}
              aria-current={active ? 'page' : undefined}
              title={collapsed ? item.label : undefined}
            >
              <Icon size={18} />
              {!collapsed ? <span>{item.label}</span> : null}
            </button>
          );
        })}
      </nav>

      <section className="recent-chat-section" aria-label="Recent chats">
        {!collapsed ? <p className="eyebrow">Recent Chats</p> : null}
        <div className="recent-chat-list">
          {recents.length > 0 ? recents.map((message, index) => (
            <button
              className={activeWorkspaceView === 'chat' && index === 0 ? 'recent-chat-row recent-chat-row-active' : 'recent-chat-row'}
              type="button"
              key={message.id}
              onClick={() => setActiveWorkspaceView('chat')}
              title={collapsed ? getRecentLabel(message) : undefined}
            >
              <MessageSquare size={16} />
              {!collapsed ? (
                <span>
                  <strong>{getRecentLabel(message)}</strong>
                  <small>{new Date(message.createdAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</small>
                </span>
              ) : null}
            </button>
          )) : (
            <button className={activeWorkspaceView === 'chat' ? 'recent-chat-row recent-chat-row-active' : 'recent-chat-row'} type="button" onClick={() => setActiveWorkspaceView('chat')} title={collapsed ? 'New chat' : undefined}>
              <MessageSquare size={16} />
              {!collapsed ? (
                <span>
                  <strong>New chat</strong>
                  <small>Ready for a first prompt</small>
                </span>
              ) : null}
            </button>
          )}
        </div>
      </section>
    </aside>
  );
}