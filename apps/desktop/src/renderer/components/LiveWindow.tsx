import { Bot, ExternalLink, PanelsTopLeft } from 'lucide-react';
import { useAppStore } from '../stores/useAppStore';

export function LiveWindow() {
  const preview = useAppStore((state) => state.preview);

  return (
    <section className="live-window">
      <header className="live-header">
        <div>
          <p className="eyebrow">Live AI Window</p>
          <h2>{preview.title}</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Detach preview">
          <ExternalLink size={17} />
        </button>
      </header>

      <div className="preview-stage">
        <div className="preview-frame">
          <div className="preview-orbit">
            <PanelsTopLeft size={34} />
          </div>
          <h3>{preview.kind === 'empty' ? 'Preview surface waiting' : preview.title}</h3>
          <p>{preview.detail}</p>
        </div>
      </div>

      <footer className="activity-strip">
        <Bot size={16} />
        <span>Future components can mount browser, UI preview, file, and task surfaces here.</span>
      </footer>
    </section>
  );
}
