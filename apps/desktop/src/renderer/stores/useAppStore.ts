import { create } from 'zustand';
import type { ChatActivity, ChatEvent, ChatMessage, McpTool, PreviewItem, WorkspaceView } from '../types';

type AppState = {
  sidebarCollapsed: boolean;
  activeWorkspaceView: WorkspaceView;
  backendUrl: string;
  mcpTools: McpTool[];
  messages: ChatMessage[];
  preview: PreviewItem;
  isStreaming: boolean;
  isScreenSharing: boolean;
  isScreenViewing: boolean;
  activeAssistantId: string | null;
  skillsRootPath: string | null;

  provider: string;
  model: string;
  apiKey: string;
  baseUrl: string;

  toggleSidebar: () => void;
  setActiveWorkspaceView: (view: WorkspaceView) => void;
  setBackendUrl: (backendUrl: string) => void;
  setMcpTools: (tools: McpTool[]) => void;
  setMcpToolStatus: (toolId: string, status: McpTool['status']) => void;
  setSkillsRootPath: (skillsRootPath: string | null) => void;

  setProvider: (provider: string) => void;
  setModel: (model: string) => void;
  setApiKey: (apiKey: string) => void;
  setBaseUrl: (baseUrl: string) => void;
  setProviderSettings: (settings: { provider: string; model: string; apiKey: string; baseUrl: string }) => void;

  addUserMessage: (content: string) => void;
  addChatEvent: (event: ChatEvent) => void;
  setStreaming: (isStreaming: boolean) => void;
  setScreenSharing: (isScreenSharing: boolean) => void;
  setScreenViewing: (isScreenViewing: boolean) => void;
};

const now = () => new Date().toISOString();
const skillsRootStorageKey = 'jarvis.skillsRootPath';

function getStoredSkillsRootPath() {
  if (typeof window === 'undefined') {
    return null;
  }
  const stored = window.localStorage.getItem(skillsRootStorageKey);
  return stored && stored.trim() ? stored : null;
}

function setStoredSkillsRootPath(path: string | null) {
  if (typeof window === 'undefined') {
    return;
  }
  if (path) {
    window.localStorage.setItem(skillsRootStorageKey, path);
  } else {
    window.localStorage.removeItem(skillsRootStorageKey);
  }
}

function appendToAssistantById(
  messages: ChatMessage[],
  assistantId: string | null,
  update: (message: ChatMessage) => ChatMessage,
) {
  if (assistantId === null) {
    return messages;
  }
  return messages.map((message) => (message.id === assistantId ? update(message) : message));
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  activeWorkspaceView: 'chat',
  backendUrl: import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8765',
  mcpTools: [
    {
      id: 'playwright',
      name: 'Playwright',
      command: 'npx',
      args: [
        '@playwright/mcp@latest',
        '--browser=chrome',
        '--caps=vision',
        '--shared-browser-context',
        '--timeout-action=10000',
        '--timeout-navigation=90000',
      ],
      status: 'running',
      auto_start: true,
      description: 'Browser automation MCP preset for agent web browsing and live preview checks.',
    },
  ],
  messages: [
    {
      id: 'system-welcome',
      role: 'system',
      content: 'Jarvis local runtime is ready for backend connection. Configure OpenRouter and grant a workspace root to unlock agent tools.',
      createdAt: now(),
    },
  ],
  preview: {
    id: 'empty-preview',
    title: 'Live AI Window',
    kind: 'empty',
    detail: 'Preview surfaces, browser sessions, generated UI, and future agent workspaces will render here.',
  },
  isStreaming: false,
  isScreenSharing: false,
  isScreenViewing: false,
  activeAssistantId: null,
  skillsRootPath: getStoredSkillsRootPath(),

  provider: 'openrouter',
  model: 'openai/gpt-4o-mini',
  apiKey: '',
  baseUrl: '',

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setActiveWorkspaceView: (activeWorkspaceView) => set({ activeWorkspaceView }),
  setBackendUrl: (backendUrl) => set({ backendUrl }),
  setMcpTools: (tools) => set({ mcpTools: tools }),
  setMcpToolStatus: (toolId, status) => set((state) => ({
    mcpTools: state.mcpTools.map((tool) => (tool.id === toolId ? { ...tool, status } : tool)),
  })),
  setSkillsRootPath: (skillsRootPath) => {
    setStoredSkillsRootPath(skillsRootPath);
    set({ skillsRootPath });
  },

  setProvider: (provider) => set({ provider }),
  setModel: (model) => set({ model }),
  setApiKey: (apiKey) => set({ apiKey }),
  setBaseUrl: (baseUrl) => set({ baseUrl }),
  setProviderSettings: ({ provider, model, apiKey, baseUrl }) => set({ provider, model, apiKey, baseUrl }),

  addUserMessage: (content) => set((state) => {
    const assistantId = crypto.randomUUID();
    return {
      activeWorkspaceView: 'chat',
      activeAssistantId: assistantId,
      messages: [
        ...state.messages,
        {
          id: crypto.randomUUID(),
          role: 'user',
          content,
          createdAt: now(),
        },
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          createdAt: now(),
          activities: [],
          thoughts: [],
          isStreaming: true,
        },
      ],
    };
  }),
  addChatEvent: (event) => set((state) => {
    if (event.type === 'done') {
      return {
        activeAssistantId: null,
        isScreenViewing: false,
        messages: appendToAssistantById(state.messages, state.activeAssistantId, (message) => ({
          ...message,
          activities: [],
          isStreaming: false,
        })),
      };
    }

    if (event.type === 'error') {
      return {
        activeAssistantId: null,
        isScreenViewing: false,
        messages: appendToAssistantById(state.messages, state.activeAssistantId, (message) => ({
          ...message,
          activities: [],
          isStreaming: false,
        })).concat({
          id: crypto.randomUUID(),
          role: 'error',
          content: event.content,
          createdAt: now(),
        }),
      };
    }

    if (event.type === 'assistant_message') {
      return {
        messages: appendToAssistantById(state.messages, state.activeAssistantId, (message) => ({
          ...message,
          content: `${message.content}${event.content}`,
        })),
      };
    }

    if (event.type === 'thought') {
      return {
        messages: appendToAssistantById(state.messages, state.activeAssistantId, (message) => ({
          ...message,
          thoughts: [...(message.thoughts ?? []), {
            id: crypto.randomUUID(),
            content: event.content,
            createdAt: now(),
          }],
        })),
      };
    }

    const activity: ChatActivity = {
      id: crypto.randomUUID(),
      type: event.type,
      content: event.content,
      toolName: event.payload?.tool_name ?? undefined,
      status: event.payload?.status ?? undefined,
      detail: event.payload?.detail ?? undefined,
    };

    return {
      isScreenViewing: event.payload?.tool_name === 'capture_desktop_screenshot_tool'
        ? event.type === 'tool_call'
        : state.isScreenViewing,
      messages: appendToAssistantById(state.messages, state.activeAssistantId, (message) => ({
        ...message,
        activities: [...(message.activities ?? []), activity],
      })),
    };
  }),
  setStreaming: (isStreaming) => set({ isStreaming }),
  setScreenSharing: (isScreenSharing) => set({ isScreenSharing }),
  setScreenViewing: (isScreenViewing) => set({ isScreenViewing }),
}));
