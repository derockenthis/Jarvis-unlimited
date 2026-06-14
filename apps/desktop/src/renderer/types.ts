export type McpToolStatus = 'running' | 'stopped' | 'error';

export type McpTool = {
  id: string;
  name: string;
  command: string;
  args: string[];
  status: McpToolStatus;
  auto_start?: boolean;
  autoStart?: boolean;
  description: string;
};

export type McpActionResponse = {
  tool_id: string;
  status: McpToolStatus | 'error';
  message: string;
};

export type ChatEventType = 'thought' | 'tool_call' | 'tool_result' | 'assistant_message' | 'done' | 'error';

export type WorkspaceView = 'chat' | 'provider' | 'mcp' | 'skills';

export type ChatEvent = {
  type: ChatEventType;
  content: string;
  payload?: {
    tool_name?: string | null;
    status?: string | null;
    detail?: string | null;
  };
};

export type ScreenShareState = {
  isShared: boolean;
  isViewing: boolean;
};

export type ChatActivity = {
  id: string;
  type: 'tool_call' | 'tool_result';
  content: string;
  toolName?: string;
  status?: string;
  detail?: string;
};

export type ChatThought = {
  id: string;
  content: string;
  createdAt: string;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  createdAt: string;
  activities?: ChatActivity[];
  thoughts?: ChatThought[];
  isStreaming?: boolean;
};

export type PreviewItem = {
  id: string;
  title: string;
  kind: 'component' | 'browser' | 'file' | 'empty';
  detail: string;
};

export type ProviderModelSettings = {
  provider: string;
  model: string;
  api_key: string;
  base_url: string;
};

export type ModelSettingsResponse = {
  current_provider: string;
  providers: ProviderModelSettings[];
};
