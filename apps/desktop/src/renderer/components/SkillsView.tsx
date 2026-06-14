import { useState } from 'react';
import { FolderOpen, Trash2 } from 'lucide-react';
import { useAppStore } from '../stores/useAppStore';

export function SkillsView() {
  const skillsRootPath = useAppStore((state) => state.skillsRootPath);
  const setSkillsRootPath = useAppStore((state) => state.setSkillsRootPath);
  const addChatEvent = useAppStore((state) => state.addChatEvent);
  const [isPickingSkillsFolder, setIsPickingSkillsFolder] = useState(false);

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
    <section className="workspace-panel">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Skills</p>
          <h2><FolderOpen size={18} /> Skills Folder</h2>
        </div>
      </header>

      <div className="workspace-copy">
        <p>Select the folder that contains reusable skills. Jarvis will search that folder first and treat <strong>skills.md</strong> there as the canonical skills index when present.</p>
      </div>

      <div className="skills-path skills-path-large">
        <span>{skillsRootPath ?? 'No skills folder selected yet.'}</span>
      </div>

      <div className="skills-actions skills-actions-inline">
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
  );
}