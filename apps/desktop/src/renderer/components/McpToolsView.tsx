import { useEffect } from 'react';
import { Circle, Play, Plus, Settings2, Square, Wrench } from 'lucide-react';
import { fetchMcpTools, startMcpTool, stopMcpTool } from '../api/backend';
import { useAppStore } from '../stores/useAppStore';

export function McpToolsView() {
  const tools = useAppStore((state) => state.mcpTools);
  const backendUrl = useAppStore((state) => state.backendUrl);
  const setMcpTools = useAppStore((state) => state.setMcpTools);
  const setMcpToolStatus = useAppStore((state) => state.setMcpToolStatus);
  const addChatEvent = useAppStore((state) => state.addChatEvent);

  useEffect(() => {
    fetchMcpTools(backendUrl).then(setMcpTools).catch((error) => {
      addChatEvent({
        type: 'error',
        content: error instanceof Error ? error.message : 'Unable to load MCP tools.',
      });
    });
  }, [addChatEvent, backendUrl, setMcpTools]);

  const toggleTool = async (toolId: string, running: boolean) => {
    try {
      const response = running
        ? await stopMcpTool(backendUrl, toolId)
        : await startMcpTool(backendUrl, toolId);
      if (response.status === 'running' || response.status === 'stopped' || response.status === 'error') {
        setMcpToolStatus(toolId, response.status);
      }
      addChatEvent({
        type: 'tool_result',
        content: response.message,
        payload: { tool_name: toolId, status: response.status },
      });
    } catch (error) {
      addChatEvent({
        type: 'error',
        content: error instanceof Error ? error.message : 'MCP action failed.',
        payload: { tool_name: toolId, status: 'error' },
      });
    }
  };

  return (
    <section className="workspace-panel">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">MCP Tools</p>
          <h2><Wrench size={18} /> Tool Control</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Add MCP tool">
          <Plus size={18} />
        </button>
      </header>

      <div className="workspace-tool-list">
        {tools.map((tool) => (
          <article className="workspace-tool-row" key={tool.id}>
            <div className="tool-card-main">
              <span className={`status-dot status-${tool.status}`}>
                <Circle size={10} fill="currentColor" />
              </span>
              <div>
                <h3>{tool.name}</h3>
                <p>{tool.description}</p>
                <code>{tool.command} {tool.args.join(' ')}</code>
              </div>
            </div>
            <div className="tool-actions">
              <button className="mini-button" type="button" onClick={() => toggleTool(tool.id, tool.status === 'running')}>
                {tool.status === 'running' ? <Square size={14} /> : <Play size={14} />}
                {tool.status === 'running' ? 'Stop' : 'Start'}
              </button>
              <button className="icon-button small" type="button" aria-label={`Configure ${tool.name}`}>
                <Settings2 size={15} />
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}