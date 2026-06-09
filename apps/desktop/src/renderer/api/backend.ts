import type { ChatEvent, McpActionResponse, McpTool } from '../types';

export async function streamChat(
  backendUrl: string,
  message: string,
  screenShareEnabled: boolean,
  skillsRootPath: string | null,
  onEvent: (event: ChatEvent) => void,
) {
  const response = await fetch(`${backendUrl}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: 'desktop-session',
      user_id: 'local-user',
      screen_share_enabled: screenShareEnabled,
      skills_root: skillsRootPath,
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

export async function transcribeAudio(backendUrl: string, audioBlob: Blob): Promise<string> {
  const formData = new FormData();
  const extension = audioBlob.type.includes('ogg') ? 'ogg' : 'webm';
  formData.append('audio', audioBlob, `speech.${extension}`);

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
