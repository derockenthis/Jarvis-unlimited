import { FormEvent, useEffect, useRef, useState } from 'react';
import { Maximize2, Mic, MicOff, Send, Sparkles, Volume2, VolumeX } from 'lucide-react';
import { streamChat, synthesizeSpeech, transcribeAudio } from '../api/backend';
import { useAppStore } from '../stores/useAppStore';
import type { ChatEvent } from '../types';

function formatMiniSpeechError(error: unknown) {
  if (error instanceof DOMException && error.name === 'NotAllowedError') {
    return 'Mic blocked';
  }

  if (error instanceof Error && /not-allowed|permission/i.test(error.message)) {
    return 'Mic blocked';
  }

  return 'Speech failed';
}

export function MiniChat() {
  const [draft, setDraft] = useState('');
  const [latestResponse, setLatestResponse] = useState('');
  const [status, setStatus] = useState('Ready');
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const setBackendUrl = useAppStore((state) => state.setBackendUrl);
  const setSessionId = useAppStore((state) => state.setSessionId);
  const providerSettingsLoaded = useAppStore((state) => state.providerSettingsLoaded);
  const loadProviderSettings = useAppStore((state) => state.loadProviderSettings);
  const sessionId = useAppStore((state) => state.sessionId);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const responseRef = useRef('');
  const spokenAudioRef = useRef<HTMLAudioElement | null>(null);
  const spokenAudioUrlRef = useRef<string | null>(null);

  const applyDesktopModelSettings = (settings: {
    provider: string;
    model: string;
    apiKey: string;
    baseUrl: string;
    speechModel: string;
  }) => {
    useAppStore.getState().setProviderSettings(settings);
    useAppStore.setState({ providerSettingsLoaded: true });
  };

  const hydrateModelSettings = async (forceRefresh = false) => {
    const desktopApi = window.jarvisDesktop;
    if (!forceRefresh && desktopApi?.getModelSettings) {
      try {
        const payload = await desktopApi.getModelSettings();
        if (payload.settings?.model?.trim()) {
          applyDesktopModelSettings({
            provider: payload.settings.provider,
            model: payload.settings.model,
            apiKey: payload.settings.apiKey,
            baseUrl: payload.settings.baseUrl,
            speechModel: payload.settings.speechModel,
          });
          return;
        }
      } catch {
        // Fall back to the backend settings API below.
      }
    }

    await loadProviderSettings(true);
  };

  useEffect(() => {
    let cancelled = false;

    const desktopApi = window.jarvisDesktop;

    desktopApi?.getBackendUrl().then((nextBackendUrl) => {
      if (cancelled) {
        return;
      }
      setBackendUrl(nextBackendUrl);
      void hydrateModelSettings();
      if (typeof desktopApi.getScreenSharingEnabled === 'function') {
        desktopApi.getScreenSharingEnabled().then((payload) => {
          if (!cancelled) {
            useAppStore.getState().setScreenSharing(payload.active);
          }
        }).catch(() => undefined);
      }
      desktopApi?.getCurrentSessionId().then((payload) => {
        if (cancelled) {
          return;
        }
        if (payload.session_id) {
          setSessionId(payload.session_id);
        } else {
          desktopApi?.setCurrentSessionId(sessionId).catch(() => undefined);
        }
      }).catch(() => undefined);
    }).catch(() => {
      void hydrateModelSettings(true);
    });

    if ('mediaDevices' in navigator && typeof MediaRecorder !== 'undefined') {
      setSpeechSupported(true);
    }

    return () => {
      cancelled = true;
      mediaRecorderRef.current?.stop();
      mediaRecorderRef.current = null;
      recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
      recordingStreamRef.current = null;
      spokenAudioRef.current?.pause();
      spokenAudioRef.current = null;
      if (spokenAudioUrlRef.current) {
        URL.revokeObjectURL(spokenAudioUrlRef.current);
        spokenAudioUrlRef.current = null;
      }
    };
  }, [loadProviderSettings, setBackendUrl, sessionId, setSessionId]);

  const cancelSpokenResponse = () => {
    spokenAudioRef.current?.pause();
    spokenAudioRef.current = null;
    if (spokenAudioUrlRef.current) {
      URL.revokeObjectURL(spokenAudioUrlRef.current);
      spokenAudioUrlRef.current = null;
    }
    window.speechSynthesis?.cancel();
  };

  const speakResponse = async (text: string) => {
    if (!ttsEnabled || !text.trim()) {
      return;
    }

    cancelSpokenResponse();

    try {
      const currentSettings = useAppStore.getState();
      const speechBlob = await synthesizeSpeech(currentSettings.backendUrl, text.trim());
      const speechUrl = URL.createObjectURL(speechBlob);
      spokenAudioUrlRef.current = speechUrl;
      const audio = new Audio(speechUrl);
      spokenAudioRef.current = audio;
      audio.onended = () => {
        if (spokenAudioUrlRef.current === speechUrl) {
          URL.revokeObjectURL(speechUrl);
          spokenAudioUrlRef.current = null;
        }
        if (spokenAudioRef.current === audio) {
          spokenAudioRef.current = null;
        }
      };
      audio.onerror = () => {
        if (spokenAudioUrlRef.current === speechUrl) {
          URL.revokeObjectURL(speechUrl);
          spokenAudioUrlRef.current = null;
        }
        if (spokenAudioRef.current === audio) {
          spokenAudioRef.current = null;
        }
      };
      await audio.play();
      return;
    } catch {
      // Fall back to the browser voice engine if the local neural model is unavailable.
    }

    if (typeof window.speechSynthesis === 'undefined') {
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text.trim());
    utterance.rate = 1;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
  };

  const handleChatEvent = (event: ChatEvent) => {
    if (event.type === 'assistant_message') {
      responseRef.current = `${responseRef.current}${event.content}`;
      setLatestResponse(responseRef.current);
      setStatus('Responding');
      return;
    }

    if (event.type === 'done') {
      setStatus('Ready');
      void speakResponse(responseRef.current);
      return;
    }

    if (event.type === 'error') {
      setStatus(event.content || 'Chat failed');
      return;
    }

    if (event.type === 'tool_call') {
      setStatus(event.payload?.tool_name ? `Using ${event.payload.tool_name}` : 'Using tool');
      return;
    }

    if (event.type === 'thought') {
      setStatus('Thinking');
    }
  };

  const forwardChatActivity = (event: ChatEvent) => {
    window.jarvisDesktop?.publishChatEvent({
      session_id: sessionId,
      event,
    }).catch(() => undefined);
  };

  const resolveScreenSharingEnabled = async () => {
    const desktopApi = window.jarvisDesktop;
    if (desktopApi && typeof desktopApi.getScreenSharingEnabled === 'function') {
      try {
        const payload = await desktopApi.getScreenSharingEnabled();
        return payload.active;
      } catch {
        return useAppStore.getState().isScreenSharing;
      }
    }
    return useAppStore.getState().isScreenSharing;
  };

  const sendDraft = async () => {
    const content = draft.trim();
    if (!content || status === 'Sending' || status === 'Responding') {
      return;
    }

    setDraft('');
    setLatestResponse('');
    responseRef.current = '';
    setStatus('Sending');

    try {
      if (!providerSettingsLoaded || !useAppStore.getState().model.trim()) {
        await hydrateModelSettings(true);
      }

      const currentSettings = useAppStore.getState();
      const screenSharingState = await resolveScreenSharingEnabled();
      await window.jarvisDesktop?.publishChatTurnStarted({
        session_id: sessionId,
        content,
      });
      await streamChat(
        currentSettings.backendUrl,
        content,
        screenSharingState,
        currentSettings.skillsRootPath,
        currentSettings.provider,
        currentSettings.model,
        currentSettings.apiKey,
        currentSettings.baseUrl,
        (event) => {
          handleChatEvent(event);
          forwardChatActivity(event);
        },
        sessionId,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Chat failed';
      forwardChatActivity({
        type: 'error',
        content: message,
      });
      setStatus(message);
    }
  };

  const transcribeRecording = async (audioBlob: Blob) => {
    if (audioBlob.size === 0) {
      setStatus('No audio');
      return;
    }

    setIsTranscribing(true);
    setStatus('Transcribing');
    try {
      const currentSettings = useAppStore.getState();
      const transcript = (await transcribeAudio(currentSettings.backendUrl, audioBlob, currentSettings.speechModel)).trim();
      if (transcript) {
        setDraft((currentDraft) => (currentDraft ? `${currentDraft} ${transcript}`.trim() : transcript));
      }
      setStatus('Ready');
    } catch (error) {
      setStatus(formatMiniSpeechError(error));
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
      setStatus('Listening');
    } catch (error) {
      setIsListening(false);
      setStatus(formatMiniSpeechError(error));
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

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await sendDraft();
  };

  return (
    <main className="mini-chat-shell">
      <form className="mini-chat-bar" onSubmit={submit}>
        <button
          className="mini-chat-icon-button"
          type="button"
          onClick={() => { void window.jarvisDesktop?.restoreMainWindowFromMiniChat(); }}
          aria-label="Open Jarvis"
          title="Open Jarvis"
        >
          <Maximize2 size={15} />
        </button>
        <div className="mini-chat-status" title={latestResponse || status}>
          {latestResponse || status}
        </div>
        <input
          aria-label="Message Jarvis"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask Jarvis..."
        />
        <button
          className={isListening || isTranscribing ? 'mini-chat-icon-button mini-chat-icon-button-active' : 'mini-chat-icon-button'}
          type="button"
          onClick={toggleSpeechRecording}
          disabled={!speechSupported || isTranscribing}
          aria-label={isListening ? 'Stop voice input' : 'Start voice input'}
          title="Voice input"
        >
          {isTranscribing ? <Sparkles size={15} /> : isListening ? <MicOff size={15} /> : <Mic size={15} />}
        </button>
        <button
          className={ttsEnabled ? 'mini-chat-icon-button mini-chat-icon-button-active-soft' : 'mini-chat-icon-button'}
          type="button"
          onClick={() => {
            cancelSpokenResponse();
            setTtsEnabled((current) => !current);
          }}
          aria-label={ttsEnabled ? 'Disable spoken responses' : 'Enable spoken responses'}
          title={ttsEnabled ? 'Spoken responses on' : 'Spoken responses off'}
        >
          {ttsEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
        </button>
        <button className="mini-chat-send-button" type="submit" aria-label="Send message" title="Send">
          <Send size={15} />
        </button>
      </form>
    </main>
  );
}
