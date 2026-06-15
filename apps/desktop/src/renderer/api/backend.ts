import type { ChatEvent, Conversation, ConversationMessage, McpActionResponse, McpTool, ModelSettingsResponse } from '../types';

export async function streamChat(
  backendUrl: string,
  message: string,
  screenShareEnabled: boolean,
  skillsRootPath: string | null,
  provider: string | null,
  model: string | null,
  apiKey: string | null,
  baseUrl: string | null,
  onEvent: (event: ChatEvent) => void,
  sessionId: string,
) {
  const response = await fetch(`${backendUrl}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      user_id: 'local-user',
      screen_share_enabled: screenShareEnabled,
      skills_root: skillsRootPath,
      provider,
      model,
      api_key: apiKey,
      base_url: baseUrl,
    }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';

    for (const chunk of chunks) {
      const line = chunk.split('\n').find((entry) => entry.startsWith('data: '));
      if (!line) {
        continue;
      }
      onEvent(JSON.parse(line.slice(6)) as ChatEvent);
    }
  }
}

export async function transcribeAudio(backendUrl: string, audioBlob: Blob, speechModel?: string): Promise<string> {
  const formData = new FormData();
  const extension = audioBlob.type.includes('ogg') ? 'ogg' : 'webm';
  formData.append('audio', audioBlob, `speech.${extension}`);
  if (speechModel) {
    formData.append('model', speechModel);
  }

  const response = await fetch(`${backendUrl}/api/speech/transcribe`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let detail = `Speech transcription failed with status ${response.status}`;
    try {
      const payload = await response.json() as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // Keep the generic status message when the server does not return JSON.
    }
    throw new Error(detail);
  }

  const payload = await response.json() as { text: string };
  return payload.text;
}

export async function fetchOllamaModels(backendUrl: string, baseUrl: string = "http://localhost:11434"): Promise<string[]> {
  const response = await fetch(`${backendUrl}/api/models/ollama?base_url=${encodeURIComponent(baseUrl)}`);
  if (!response.ok) {
    return [];
  }
  const payload = await response.json() as { models: string[] };
  return payload.models || [];
}

export async function fetchModelSettings(backendUrl: string): Promise<ModelSettingsResponse> {
  const response = await fetch(`${backendUrl}/api/settings/model`);
  if (!response.ok) {
    throw new Error(`Model settings request failed with status ${response.status}`);
  }
  return response.json() as Promise<ModelSettingsResponse>;
}

export async function saveModelSettings(
  backendUrl: string,
  payload: { provider: string; model: string; api_key: string; base_url: string; speech_model?: string },
): Promise<ModelSettingsResponse> {
  const response = await fetch(`${backendUrl}/api/settings/model`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Save model settings failed with status ${response.status}`);
  }
  return response.json() as Promise<ModelSettingsResponse>;
}

export async function fetchMcpTools(backendUrl: string): Promise<McpTool[]> {
  const response = await fetch(`${backendUrl}/api/mcp/tools`);
  if (!response.ok) {
    throw new Error(`MCP tools request failed with status ${response.status}`);
  }
  const payload = await response.json() as { tools: McpTool[] };
  return payload.tools;
}

export async function startMcpTool(backendUrl: string, toolId: string): Promise<McpActionResponse> {
  const response = await fetch(`${backendUrl}/api/mcp/tools/${toolId}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: 'local-user' }),
  });
  if (!response.ok) {
    throw new Error(`Start MCP tool failed with status ${response.status}`);
  }
  return response.json() as Promise<McpActionResponse>;
}

export async function stopMcpTool(backendUrl: string, toolId: string): Promise<McpActionResponse> {
  const response = await fetch(`${backendUrl}/api/mcp/tools/${toolId}/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: 'local-user' }),
  });
  if (!response.ok) {
    throw new Error(`Stop MCP tool failed with status ${response.status}`);
  }
  return response.json() as Promise<McpActionResponse>;
}

export async function createConversation(
  backendUrl: string,
  userId: string = 'local-user',
  title: string = 'New Chat'
): Promise<Conversation> {
  const response = await fetch(`${backendUrl}/api/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, title }),
  });
  if (!response.ok) {
    throw new Error(`Create conversation failed with status ${response.status}`);
  }
  return response.json() as Promise<Conversation>;
}

export async function listConversations(
  backendUrl: string,
  userId: string = 'local-user',
  limit: number = 50
): Promise<Conversation[]> {
  const response = await fetch(`${backendUrl}/api/conversations?user_id=${encodeURIComponent(userId)}&limit=${limit}`);
  if (!response.ok) {
    throw new Error(`List conversations failed with status ${response.status}`);
  }
  return response.json() as Promise<Conversation[]>;
}

export async function getConversation(
  backendUrl: string,
  conversationId: string
): Promise<Conversation> {
  const response = await fetch(`${backendUrl}/api/conversations/${conversationId}`);
  if (!response.ok) {
    throw new Error(`Get conversation failed with status ${response.status}`);
  }
  return response.json() as Promise<Conversation>;
}

export async function getConversationMessages(
  backendUrl: string,
  conversationId: string
): Promise<ConversationMessage[]> {
  const response = await fetch(`${backendUrl}/api/conversations/${conversationId}/messages`);
  if (!response.ok) {
    throw new Error(`Get conversation messages failed with status ${response.status}`);
  }
  return response.json() as Promise<ConversationMessage[]>;
}

export async function updateConversationTitle(
  backendUrl: string,
  conversationId: string,
  title: string
): Promise<Conversation> {
  const response = await fetch(`${backendUrl}/api/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error(`Update conversation title failed with status ${response.status}`);
  }
  return response.json() as Promise<Conversation>;
}

export async function deleteConversation(
  backendUrl: string,
  conversationId: string
): Promise<void> {
  const response = await fetch(`${backendUrl}/api/conversations/${conversationId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Delete conversation failed with status ${response.status}`);
  }
}
