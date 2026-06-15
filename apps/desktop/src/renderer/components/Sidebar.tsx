import { ChevronLeft, ChevronRight, FolderOpen, MessageSquare, Settings, Wrench } from 'lucide-react';
import { useEffect } from 'react';
import { useAppStore } from '../stores/useAppStore';
import type { WorkspaceView } from '../types';

type NavItem = {
  view: WorkspaceView;
  label: string;
  icon: typeof Settings;
};

const navItems: NavItem[] = [
  { view: 'settings', label: 'Settings', icon: Settings },
  { view: 'mcp', label: 'MCP Tools', icon: Wrench },
  { view: 'skills', label: 'Skills', icon: FolderOpen },
];

export function Sidebar() {
  const collapsed = useAppStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const activeWorkspaceView = useAppStore((state) => state.activeWorkspaceView);
  const activeConversationId = useAppStore((state) => state.activeConversationId);
  const setActiveWorkspaceView = useAppStore((state) => state.setActiveWorkspaceView);
  const setActiveConversationId = useAppStore((state) => state.setActiveConversationId);
  const setSessionId = useAppStore((state) => state.setSessionId);
  const addNewConversation = useAppStore((state) => state.addNewConversation);
  const populateConversations = useAppStore((state) => state.populateConversations);
  const conversation = useAppStore((state) => state.conversation);

  useEffect(() => {
    void populateConversations().catch((error) => {
      console.error('Failed to load conversations', error);
    });
  }, [populateConversations]);

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
        <button className={activeWorkspaceView === 'chat' && activeConversationId === null ? 'recent-chat-row recent-chat-row-active' : 'recent-chat-row'} type="button" onClick={() => addNewConversation()} title={collapsed ? 'New chat' : undefined}>
          <MessageSquare size={16} />
          {!collapsed ? (
            <span>
              <strong>New chat</strong>
            </span>
          ) : null}
        </button>
        <div className="recent-chat-list">
          {conversation.length > 0 ? conversation.map((message) => (
            <button
              className={activeWorkspaceView === 'chat' && activeConversationId === message.id ? 'recent-chat-row recent-chat-row-active' : 'recent-chat-row'}
              type="button"
              key={message.id}
              title={`${message.title} · ${new Date(message.createdAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`}
              onClick={() => {
                setSessionId(message.id);
                setActiveConversationId(message.id);
                setActiveWorkspaceView('chat');
              }}
            >
              <MessageSquare size={16} />
              {!collapsed ? (
                <span>
                  <strong>{message.title}</strong>
                  <small>{new Date(message.createdAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</small>
                </span>
              ) : null}
            </button>
          )): (
            <div className="no-recent-chats">
              <p>No recent chats</p>
            </div>
          )}
        </div>
      </section>
    </aside>
  );
}
