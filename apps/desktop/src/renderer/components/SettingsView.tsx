import { useEffect, useState } from 'react';
import { Cpu, Mic, Sparkles } from 'lucide-react';
import { fetchModelSettings, fetchOllamaModels, saveModelSettings } from '../api/backend';
import { useAppStore } from '../stores/useAppStore';
import type { ProviderModelSettings } from '../types';

function defaultModelForProvider(provider: string) {
  return '';
}

function defaultBaseUrlForProvider(provider: string) {
  return provider === 'ollama' ? 'http://localhost:11434' : '';
}

export function SettingsView() {
  const backendUrl = useAppStore((state) => state.backendUrl);
  const addChatEvent = useAppStore((state) => state.addChatEvent);
  const provider = useAppStore((state) => state.provider);
  const model = useAppStore((state) => state.model);
  const apiKey = useAppStore((state) => state.apiKey);
  const baseUrl = useAppStore((state) => state.baseUrl);
  const speechModel = useAppStore((state) => state.speechModel);
  const setModel = useAppStore((state) => state.setModel);
  const setApiKey = useAppStore((state) => state.setApiKey);
  const setBaseUrl = useAppStore((state) => state.setBaseUrl);
  const setSpeechModel = useAppStore((state) => state.setSpeechModel);
  const setProviderSettings = useAppStore((state) => state.setProviderSettings);

  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [isSavingModelSettings, setIsSavingModelSettings] = useState(false);
  const [settingsReady, setSettingsReady] = useState(false);
  const [savedProfiles, setSavedProfiles] = useState<Record<string, ProviderModelSettings>>({});

  useEffect(() => {
    let cancelled = false;

    fetchModelSettings(backendUrl).then((response) => {
      if (cancelled) {
        return;
      }
      const nextSavedProfiles = Object.fromEntries(
        response.providers.map((entry) => [entry.provider, entry]),
      );
      const activeProvider = response.current_provider || 'openrouter';
      const activeProfile = nextSavedProfiles[activeProvider];
      setSavedProfiles(nextSavedProfiles);
      setProviderSettings({
        provider: activeProvider,
        model: activeProfile?.model || defaultModelForProvider(activeProvider),
        apiKey: activeProfile?.api_key || '',
        baseUrl: activeProfile?.base_url || defaultBaseUrlForProvider(activeProvider),
        speechModel: activeProfile?.speech_model || 'mlx-community/whisper-large-v3-turbo',
      });
      void window.jarvisDesktop?.setModelSettings({
        provider: activeProvider,
        model: activeProfile?.model || defaultModelForProvider(activeProvider),
        apiKey: activeProfile?.api_key || '',
        baseUrl: activeProfile?.base_url || defaultBaseUrlForProvider(activeProvider),
        speechModel: activeProfile?.speech_model || 'mlx-community/whisper-large-v3-turbo',
      });
      setSettingsReady(true);
    }).catch((error) => {
      addChatEvent({
        type: 'error',
        content: error instanceof Error ? error.message : 'Unable to load saved model settings.',
      });
      setSettingsReady(true);
    });

    return () => {
      cancelled = true;
    };
  }, [addChatEvent, backendUrl, setProviderSettings]);

  useEffect(() => {
    if (provider !== 'ollama') {
      return;
    }

    fetchOllamaModels(backendUrl, baseUrl || 'http://localhost:11434').then((models) => {
      setOllamaModels(models);
      if (models.length > 0 && (!model || !models.includes(model))) {
        setModel(models[0]);
      }
    }).catch(() => setOllamaModels([]));
  }, [provider, backendUrl, baseUrl, model, setModel]);

  useEffect(() => {
    if (!settingsReady) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      if (!model.trim()) {
        setIsSavingModelSettings(false);
        return;
      }

      setIsSavingModelSettings(true);
      saveModelSettings(backendUrl, {
        provider,
        model,
        api_key: apiKey,
        base_url: baseUrl,
        speech_model: speechModel,
      }).then((response) => {
        setSavedProfiles(Object.fromEntries(response.providers.map((entry) => [entry.provider, entry])));
        const activeProfile = response.providers.find((entry) => entry.provider === response.current_provider);
        void window.jarvisDesktop?.setModelSettings({
          provider: response.current_provider,
          model: activeProfile?.model || '',
          apiKey: activeProfile?.api_key || '',
          baseUrl: activeProfile?.base_url || '',
          speechModel: activeProfile?.speech_model || '',
        });
      }).catch((error) => {
        addChatEvent({
          type: 'error',
          content: error instanceof Error ? error.message : 'Unable to save model settings.',
        });
      }).finally(() => {
        setIsSavingModelSettings(false);
      });
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [settingsReady, backendUrl, provider, model, apiKey, baseUrl, speechModel, addChatEvent]);

  const handleProviderChange = (nextProvider: string) => {
    const savedProfile = savedProfiles[nextProvider];
    setProviderSettings({
      provider: nextProvider,
      model: savedProfile?.model || defaultModelForProvider(nextProvider),
      apiKey: savedProfile?.api_key || '',
      baseUrl: savedProfile?.base_url || defaultBaseUrlForProvider(nextProvider),
      speechModel: savedProfile?.speech_model || 'mlx-community/whisper-large-v3-turbo',
    });
  };

  return (
    <section className="workspace-panel">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Settings</p>
          <h2><Cpu size={18} /> LLM & Speech Models</h2>
        </div>
        {isSavingModelSettings ? (
          <div className="workspace-status"><Sparkles size={15} /> Saving</div>
        ) : null}
      </header>

      <div className="settings-form">
        <label className="field-row">
          <span>LLM Provider</span>
          <select value={provider} onChange={(event) => handleProviderChange(event.target.value)} className="text-input">
            <option value="openrouter">OpenRouter</option>
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama (Local)</option>
          </select>
        </label>

        {provider === 'ollama' ? (
          <>
            <label className="field-row">
              <span>Ollama URL</span>
              <input type="text" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="http://localhost:11434" className="text-input" />
            </label>
            <label className="field-row">
              <span>LLM Model</span>
              <select value={model} onChange={(event) => setModel(event.target.value)} className="text-input">
                {ollamaModels.length === 0 ? <option value={model}>{model || 'Loading...'}</option> : null}
                {ollamaModels.map((ollamaModel) => (
                  <option key={ollamaModel} value={ollamaModel}>{ollamaModel}</option>
                ))}
              </select>
            </label>
          </>
        ) : (
          <>
            <label className="field-row">
              <span>API Key</span>
              <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="sk-..." className="text-input" />
            </label>
            <label className="field-row">
              <span>LLM Model</span>
              <input type="text" value={model} onChange={(event) => setModel(event.target.value)} placeholder="Enter a model name" className="text-input" />
            </label>
            <label className="field-row">
              <span>Base URL (Optional)</span>
              <input type="text" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.openai.com/v1" className="text-input" />
            </label>
          </>
        )}

        <div className="settings-divider">
          <span>Speech to Text</span>
        </div>

        <label className="field-row">
          <span>Speech Model</span>
          <input type="text" value={speechModel} onChange={(event) => setSpeechModel(event.target.value)} placeholder="mlx-community/whisper-large-v3-turbo" className="text-input" />
        </label>

        <p className="settings-hint">
          Use <code>mlx-community/whisper-large-v3-turbo</code> for local transcription (requires mlx-whisper + ffmpeg), 
          or <code>openrouter/qwen/qwen3-asr-flash-2026-02-10</code> for cloud transcription via OpenRouter.
        </p>
      </div>
    </section>
  );
}
