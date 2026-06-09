import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Circle, FolderOpen, Play, Plus, Settings2, Square, Trash2 } from 'lucide-react';
import { fetchMcpTools, startMcpTool, stopMcpTool } from '../api/backend';
import { useAppStore } from '../stores/useAppStore';

export function Sidebar() {
  const collapsed = useAppStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const tools = useAppStore((state) => state.mcpTools);
  const backendUrl = useAppStore((state) => state.backendUrl);
  const skillsRootPath = useAppStore((state) => state.skillsRootPath);
  const setMcpTools = useAppStore((state) => state.setMcpTools);
  const setMcpToolStatus = useAppStore((state) => state.setMcpToolStatus);
  const setSkillsRootPath = useAppStore((state) => state.setSkillsRootPath);
  const addChatEvent = useAppStore((state) => state.addChatEvent);
  const [isPickingSkillsFolder, setIsPickingSkillsFolder] = useState(false);

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

  const pickSkillsFolder = async () => {
    try {
      setIsPickingSkillsFolder(true);
      const folderPath = await window.jarvisDesktop?.pickSkillsFolder();
      if (folderPath) {
        setSkillsRootPath(folderPath);
        addChatEvent({
          type: 'tool_result',
          content: 'Skills folder selected.',
          payload: { tool_name: 'skills_folder', status: 'success', detail: folderPath },
        });
      }
    } catch (error) {
      addChatEvent({
        type: 'error',
        content: error instanceof Error ? error.message : 'Unable to select a skills folder.',
      });
    } finally {
      setIsPickingSkillsFolder(false);
    }
  };

  return (
    <aside className={collapsed ? 'sidebar sidebar-collapsed' : 'sidebar'}>
      <div className="sidebar-topline" />
      <div className="sidebar-header">
        {!collapsed && (
          <div>
            <p className="eyebrow">Workspace</p>
            <h1>Jarvis</h1>
          </div>
        )}
        <button className="icon-button" type="button" onClick={toggleSidebar} aria-label="Toggle sidebar">
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <section className="sidebar-section">
        {!collapsed && (
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">MCP Toolset</p>
              <h2>Tools</h2>
            </div>
            <button className="icon-button" type="button" aria-label="Add MCP tool">
              <Plus size={18} />
            </button>
          </div>
        )}

        <div className="tool-list">
          {tools.map((tool) => (
            <article className="tool-card" key={tool.id}>
              <div className="tool-card-main">
                <span className={`status-dot status-${tool.status}`}>
                  <Circle size={10} fill="currentColor" />
                </span>
                {!collapsed && (
                  <div>
                    <h3>{tool.name}</h3>
                    <p>{tool.command} {tool.args.join(' ')}</p>
                  </div>
                )}
              </div>
              {!collapsed && (
                <div className="tool-actions">
                  <button className="mini-button" type="button" onClick={() => toggleTool(tool.id, tool.status === 'running')}>
                    {tool.status === 'running' ? <Square size={14} /> : <Play size={14} />}
                    {tool.status === 'running' ? 'Stop' : 'Start'}
                  </button>
                  <button className="icon-button small" type="button" aria-label={`Configure ${tool.name}`}>
                    <Settings2 size={15} />
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      </section>

      {!collapsed && (
        <section className="sidebar-section muted-panel">
          <p className="eyebrow">Skills</p>
          <h2>Skills Folder</h2>
          <p>
            Select the folder that contains reusable skills. Jarvis will search that folder first and
            treat <strong>skills.md</strong> there as the canonical skills index when present.
          </p>
          <div className="skills-path">
            <span>{skillsRootPath ?? 'No skills folder selected yet.'}</span>
          </div>
          <div className="skills-actions">
            <button className="secondary-button" type="button" onClick={pickSkillsFolder} disabled={isPickingSkillsFolder}>
              <FolderOpen size={16} />
              {skillsRootPath ? 'Change skills folder' : 'Select skills folder'}
            </button>
            {skillsRootPath ? (
              <button className="secondary-button secondary-button-ghost" type="button" onClick={() => setSkillsRootPath(null)}>
                <Trash2 size={16} />
                Clear
              </button>
            ) : null}
          </div>
        </section>
      )}
    </aside>
  );
}
