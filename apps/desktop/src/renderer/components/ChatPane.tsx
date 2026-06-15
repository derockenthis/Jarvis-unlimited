import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import { Mic, MicOff, MonitorUp, Send, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { streamChat, transcribeAudio } from '../api/backend';
import { useAppStore } from '../stores/useAppStore';

function getActivityPreview(detail: string | undefined, content: string) {
  const source = detail ?? content;
  if (source.length <= 280) {
    return source;
  }
  return `${source.slice(0, 280)}...`;
}

function isTableRow(line: string) {
  return /^\|(?:[^|\n]*\|)+\s*$/.test(line.trim());
}

function normalizeAssistantMarkdown(content: string) {
  const normalizedLines = content
    .replace(/\r\n/g, '\n')
    .replace(/\*\*([^*\n]+?)\*\*/g, (_, boldText: string) => `**${boldText.trim()}**`)
    .replace(/\*\*([^*\n]+:)\*\*\s+\*\*([^*\n]+)\*\*/g, '**$1** $2')
    .replace(/^(\s{0,3}#{1,6})(\S)/gm, '$1 $2')
    .replace(/^(\s*\d+\.)(\S)/gm, '$1 $2')
    .replace(/^(\s*[-*])(\S)/gm, '$1 $2')
    .replace(/([:.])(\*\*)/g, '$1 $2')
    .replace(/(\*\*[^*]+\*\*)(?=\w)/g, '$1 ')
    .replace(/(?<=\w)(\*\*[^*]+\*\*)/g, ' $1')
    .split('\n');

  return normalizedLines
    .filter((line, index, lines) => {
      if (line.trim() !== '') {
        return true;
      }

      return !(isTableRow(lines[index - 1] ?? '') && isTableRow(lines[index + 1] ?? ''));
    })
    .join('\n');
}

function renderAssistantContent(content: string) {
  return (
    <div className="assistant-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeAssistantMarkdown(content)}</ReactMarkdown>
    </div>
  );
}

function renderThoughtPanel(message: { thoughts?: { id: string; content: string }[]; isStreaming?: boolean }) {
  if (!message.thoughts?.length) {
    return null;
  }

  return (
    <details className="thought-panel" open={message.isStreaming}>
      <summary>
        <Sparkles size={14} />
        Agent thoughts
        <span>{message.thoughts.length}</span>
      </summary>
      <ol>
        {message.thoughts.map((thought) => (
          <li key={thought.id}>{thought.content}</li>
        ))}
      </ol>
    </details>
  );
}

export function ChatPane() {
  const [draft, setDraft] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const messages = useAppStore((state) => state.messages);
  const backendUrl = useAppStore((state) => state.backendUrl);
  const skillsRootPath = useAppStore((state) => state.skillsRootPath);
  const isStreaming = useAppStore((state) => state.isStreaming);
  const isScreenSharing = useAppStore((state) => state.isScreenSharing);
  const addUserMessage = useAppStore((state) => state.addUserMessage);
  const addChatEvent = useAppStore((state) => state.addChatEvent);
  const populateConversations = useAppStore((state) => state.populateConversations);
  const setStreaming = useAppStore((state) => state.setStreaming);
  const setScreenSharing = useAppStore((state) => state.setScreenSharing);
  const sessionId = useAppStore((state) => state.sessionId);
  const speechModel = useAppStore((state) => state.speechModel);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      return;
    }
    setSpeechSupported(true);

    return () => {
      mediaRecorderRef.current?.stop();
      mediaRecorderRef.current = null;
      recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
      recordingStreamRef.current = null;
    };
  }, [addChatEvent]);

  const formatSpeechError = (error: unknown) => {
    if (error instanceof DOMException && error.name === 'NotAllowedError') {
      return 'Microphone access was denied. Allow microphone access for Jarvis or Electron in macOS Privacy & Security, then relaunch the app.';
    }

    if (error instanceof Error && /not-allowed|permission/i.test(error.message)) {
      return 'Microphone access was denied. Allow microphone access for Jarvis or Electron in macOS Privacy & Security, then relaunch the app.';
    }

    if (error instanceof Error) {
      return `Speech to text failed: ${error.message}`;
    }

    return 'Speech to text failed to start.';
  };

  const transcribeRecording = async (audioBlob: Blob) => {
    if (audioBlob.size === 0) {
      addChatEvent({
        type: 'error',
        content: 'Speech to text failed: no audio was captured.',
      });
      return;
    }

    setIsTranscribing(true);
    try {
      const transcript = (await transcribeAudio(backendUrl, audioBlob, speechModel)).trim();
      if (transcript) {
        setDraft((currentDraft) => (currentDraft ? `${currentDraft} ${transcript}`.trim() : transcript));
      }
    } catch (error) {
      addChatEvent({
        type: 'error',
        content: formatSpeechError(error),
      });
    } finally {
      setIsTranscribing(false);
    }
  };

  const startSpeechRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeTypeCandidates = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg',
      ];
      const supportedMimeType = mimeTypeCandidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const recorder = supportedMimeType ? new MediaRecorder(stream, { mimeType: supportedMimeType }) : new MediaRecorder(stream);

      recordingStreamRef.current = stream;
      recordedChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };
      recorder.onerror = () => {
        setIsListening(false);
        recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
        recordingStreamRef.current = null;
        mediaRecorderRef.current = null;
        addChatEvent({
          type: 'error',
          content: 'Speech to text failed while recording audio.',
        });
      };
      recorder.onstop = () => {
        setIsListening(false);
        const chunks = recordedChunksRef.current.slice();
        recordedChunksRef.current = [];
        mediaRecorderRef.current = null;
        recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
        recordingStreamRef.current = null;
        void transcribeRecording(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }));
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsListening(true);
    } catch (error) {
      setIsListening(false);
      addChatEvent({
        type: 'error',
        content: formatSpeechError(error),
      });
    }
  };

  const toggleSpeechRecording = async () => {
    if (!speechSupported || isTranscribing) {
      return;
    }

    if (isListening) {
      mediaRecorderRef.current?.stop();
      return;
    }

    await startSpeechRecording();
  };

  const provider = useAppStore((state) => state.provider);
  const model = useAppStore((state) => state.model);
  const apiKey = useAppStore((state) => state.apiKey);
  const baseUrl = useAppStore((state) => state.baseUrl);
  const sendDraft = async () => {
    const content = draft.trim();
    if (!content || isStreaming) {
      return;
    }
    mediaRecorderRef.current?.stop();
    setIsListening(false);

    setDraft('');
    setStreaming(true);
    try {
      addUserMessage(content);
      await streamChat(backendUrl, content, isScreenSharing, skillsRootPath, provider, model, apiKey, baseUrl, addChatEvent, sessionId);
    } catch (error) {
      addChatEvent({
        type: 'error',
        content: error instanceof Error ? error.message : 'Chat stream failed.',
      });
    } finally {
      setStreaming(false);
      void populateConversations().catch((error) => {
        console.error('Failed to refresh conversations', error);
      });
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await sendDraft();
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) {
      return;
    }

    event.preventDefault();
    void sendDraft();
  };

  return (
    <section className="chat-pane">
      <header className="chat-header">
        <div>
          <p className="eyebrow">Agent Chat</p>
          <h2>Ask Jarvis</h2>
        </div>
        <div className="chat-header-actions">
          <div className={isScreenSharing ? 'screen-share-status screen-share-status-active' : 'screen-share-status'}>
            <span />
            {isScreenSharing ? 'Screen sharing on' : 'Screen sharing off'}
          </div>
          <div className="connection-pill">
            <Sparkles size={15} />
            {backendUrl}
          </div>
        </div>
      </header>

      <div className="message-list">
        {messages.map((message) => (
          <article className={`message message-${message.role}`} key={message.id}>
            <span className="message-role-label">{message.role}</span>
            {message.role === 'assistant' ? renderThoughtPanel(message) : null}
            {message.activities?.length ? (
              <ol className="message-activity-list">
                {message.activities.map((activity) => (
                  <li className={`activity activity-${activity.type}`} key={activity.id}>
                    <strong>
                      {activity.type === 'tool_call' ? 'tool call' : 'tool result'}
                      {activity.toolName ? ` / ${activity.toolName}` : ''}
                      {activity.status ? ` / ${activity.status}` : ''}
                    </strong>
                    <small>{getActivityPreview(activity.detail, activity.content)}</small>
                  </li>
                ))}
              </ol>
            ) : null}
            {message.content ? (
              <div className="message-content">
                {message.role === 'assistant' ? renderAssistantContent(message.content) : <p>{message.content}</p>}
              </div>
            ) : null}
          </article>
        ))}
      </div>

      <form className="composer" onSubmit={submit}>
        <div className="composer-toolbar">
          <button
            className={isScreenSharing ? 'screen-share-button screen-share-button-active' : 'screen-share-button'}
            type="button"
            onClick={() => setScreenSharing(!isScreenSharing)}
            aria-pressed={isScreenSharing}
          >
            <MonitorUp size={16} />
            {isScreenSharing ? 'stop sharing screen' : 'share screen with agent'}
          </button>
          <button
            className={isListening || isTranscribing ? 'mic-button mic-button-active' : 'mic-button'}
            type="button"
            onClick={toggleSpeechRecording}
            disabled={!speechSupported || isTranscribing}
            aria-pressed={isListening || isTranscribing}
            aria-label={isListening ? 'Stop speech to text' : isTranscribing ? 'Transcribing speech' : 'Start speech to text'}
            title={speechSupported ? 'Speech to text' : 'Speech to text unavailable'}
          >
            {isTranscribing ? <Sparkles size={18} /> : isListening ? <MicOff size={18} /> : <Mic size={18} />}
          </button>
          {isTranscribing ? <span className="speech-status">Transcribing</span> : isListening ? <span className="speech-status">Listening</span> : null}
        </div>
        {skillsRootPath ? (
          <div className="skills-hint">
            Skills folder: <strong>{skillsRootPath}</strong>
          </div>
        ) : null}
        <div className="composer-input-row">
          <textarea
            aria-label="Message Jarvis"
            placeholder="Ask Jarvis to inspect a repo, wire an MCP, or create a UI component..."
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleComposerKeyDown}
          />
          <button className="send-button" type="submit" aria-label="Send message">
            {isStreaming ? <Sparkles size={18} /> : <Send size={18} />}
          </button>
        </div>
      </form>
    </section>
  );
}
