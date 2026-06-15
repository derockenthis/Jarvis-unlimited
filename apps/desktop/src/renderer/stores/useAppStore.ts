import { create } from 'zustand';
import { listConversations } from '../api/backend';
import type { ChatActivity, ChatEvent, ChatMessage, McpTool, PreviewItem, WorkspaceView, Conversationlist } from '../types';

type AppState = {
  sidebarCollapsed: boolean;
  activeWorkspaceView: WorkspaceView;
  backendUrl: string;
  mcpTools: McpTool[];
  messages: ChatMessage[];
  conversation: Conversationlist[];
  preview: PreviewItem;
  isStreaming: boolean;
  isScreenSharing: boolean;
  isScreenViewing: boolean;
  activeAssistantId: string | null;
  activeConversationId: string | null;
  skillsRootPath: string | null;

  provider: string;
  model: string;
  apiKey: string;
  sessionId: string;
  baseUrl: string;
  speechModel: string;

  toggleSidebar: () => void;
  setActiveWorkspaceView: (view: WorkspaceView) => void;
  setBackendUrl: (backendUrl: string) => void;
  setMcpTools: (tools: McpTool[]) => void;
  setMcpToolStatus: (toolId: string, status: McpTool['status']) => void;
  setSkillsRootPath: (skillsRootPath: string | null) => void;
  setSessionId: (sessionId: string) => void;
  setActiveConversationId: (conversationId: string | null) => void;
  setProvider: (provider: string) => void;
  setModel: (model: string) => void;
  setApiKey: (apiKey: string) => void;
  setBaseUrl: (baseUrl: string) => void;
  setSpeechModel: (speechModel: string) => void;
  setProviderSettings: (settings: { provider: string; model: string; apiKey: string; baseUrl: string; speechModel: string }) => void;
  addNewConversation: () => void;
  populateConversations: () => Promise<void>;
  addChatEvent: (event: ChatEvent) => void;
  setStreaming: (isStreaming: boolean) => void;
  setScreenSharing: (isScreenSharing: boolean) => void;
  setScreenViewing: (isScreenViewing: boolean) => void;
};

const now = () => new Date().toISOString();
const skillsRootStorageKey = 'jarvis.skillsRootPath';

function createInitialMessages(): ChatMessage[] {
  return [
    {
      id: 'system-welcome',
      role: 'system',
      content: 'Jarvis local runtime is ready for backend connection. Configure OpenRouter and grant a workspace root to unlock agent tools.',
      createdAt: now(),
    },
  ];
}

function generateSessionId() {
  return `desktop-session-${crypto.randomUUID()}`;
}

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

export const useAppStore = create<AppState>((set, get) => ({
  sessionId: generateSessionId(),
  sidebarCollapsed: false,
  activeWorkspaceView: 'chat',
  conversation: [],
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
  messages: createInitialMessages(),
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
  activeConversationId: null,
  skillsRootPath: getStoredSkillsRootPath(),

  provider: 'openrouter',
  model: 'openai/gpt-4o-mini',
  apiKey: '',
  baseUrl: '',
  speechModel: 'mlx-community/whisper-large-v3-turbo',

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
  setSessionId: (sessionId) => set({ sessionId }),
  setActiveConversationId: (activeConversationId) => set({ activeConversationId }),
  setProvider: (provider) => set({ provider }),
  setModel: (model) => set({ model }),
  setApiKey: (apiKey) => set({ apiKey }),
  setBaseUrl: (baseUrl) => set({ baseUrl }),
  setSpeechModel: (speechModel) => set({ speechModel }),
  setProviderSettings: ({ provider, model, apiKey, baseUrl, speechModel }) => set({ provider, model, apiKey, baseUrl, speechModel }),

  addNewConversation: () => set((state) => {
    const sessionId = generateSessionId();

    return {
      activeWorkspaceView: 'chat',
      activeAssistantId: null,
      activeConversationId: null,
      isStreaming: false,
      isScreenViewing: false,
      sessionId,
      messages: createInitialMessages(),
      conversation: state.conversation,
    };
  }),

  populateConversations: async () => {
    const conversations = await listConversations(get().backendUrl);
    set({
      conversation: conversations.map((conversation) => ({
        id: conversation.id,
        title: conversation.title,
        createdAt: conversation.created_at,
      })),
    });
  },

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
