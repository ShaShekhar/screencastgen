import { useEffect, useRef, useState } from "react";
import {
  listLanguages,
  listVoices,
  previewVoice,
  voiceAudioUrl,
} from "../api/voices";
import {
  AudioConfig,
  BundledVoice,
  HighlightConfig,
  LanguageOption,
  UploadedFile,
} from "../types";
import FileUploader from "./FileUploader";

interface Props {
  config: HighlightConfig | AudioConfig;
  onChange: (c: Partial<HighlightConfig>) => void;
}

const FALLBACK_LANGUAGES: LanguageOption[] = [
  { code: "en-US", name: "English (US)" },
];

type VoiceSource = "bundled" | "upload";

export default function VoiceSettings({ config, onChange }: Props) {
  const highlightCfg = config as HighlightConfig;

  const [voices, setVoices] = useState<BundledVoice[]>([]);
  const [languages, setLanguages] = useState<LanguageOption[]>(FALLBACK_LANGUAGES);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [voiceSource, setVoiceSource] = useState<VoiceSource>(
    highlightCfg.ref_audio_file_id ? "upload" : "bundled"
  );
  const [uploadedRefName, setUploadedRefName] = useState<string | null>(null);

  // Sample preview state
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listVoices(), listLanguages()])
      .then(([vs, ls]) => {
        if (cancelled) return;
        setVoices(vs);
        if (ls.length > 0) setLanguages(ls);
        // Default-select first available bundled voice if none chosen.
        if (!highlightCfg.voice_id && !highlightCfg.ref_audio_file_id) {
          const firstAvailable = vs.find((v) => v.available);
          if (firstAvailable) {
            onChange({
              voice_id: firstAvailable.id,
              language: firstAvailable.language || config.language,
            });
          }
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setLoadError(e instanceof Error ? e.message : "Failed to load voice library");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Revoke previous blob URLs to avoid leaks.
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  const setPreview = (url: string | null) => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = url;
    setPreviewUrl(url);
  };

  const handleVoiceSelect = (voice: BundledVoice) => {
    onChange({
      voice_id: voice.id,
      ref_audio_file_id: null,
      ref_text: null,
      language: voice.language || config.language,
    });
  };

  const handleSourceChange = (source: VoiceSource) => {
    setVoiceSource(source);
    if (source === "bundled") {
      onChange({ ref_audio_file_id: null });
    } else {
      onChange({ voice_id: null });
    }
  };

  const handleGenerateSample = async () => {
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const url = await previewVoice({
        language: config.language,
        voice_id: voiceSource === "bundled" ? highlightCfg.voice_id || undefined : undefined,
        ref_audio_file_id:
          voiceSource === "upload" ? highlightCfg.ref_audio_file_id || undefined : undefined,
        ref_text: highlightCfg.ref_text || undefined,
      });
      setPreview(url);
    } catch (e: unknown) {
      setPreviewError(e instanceof Error ? e.message : "Failed to generate sample");
    } finally {
      setPreviewLoading(false);
    }
  };

  const canPreview =
    !previewLoading &&
    ((voiceSource === "bundled" && !!highlightCfg.voice_id) ||
      (voiceSource === "upload" && !!highlightCfg.ref_audio_file_id));

  return (
    <div className="space-y-5">
      {/* Voice source toggle */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Voice</label>
        <div className="inline-flex rounded-lg border border-gray-200 p-0.5 bg-gray-50">
          <button
            type="button"
            onClick={() => handleSourceChange("bundled")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition ${
              voiceSource === "bundled"
                ? "bg-white text-indigo-700 shadow-sm"
                : "text-gray-500"
            }`}
          >
            Voice library
          </button>
          <button
            type="button"
            onClick={() => handleSourceChange("upload")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition ${
              voiceSource === "upload"
                ? "bg-white text-indigo-700 shadow-sm"
                : "text-gray-500"
            }`}
          >
            Upload your own
          </button>
        </div>
      </div>

      {/* Bundled voice picker */}
      {voiceSource === "bundled" && (
        <div>
          {loadError && (
            <p className="text-xs text-red-600 mb-2">{loadError}</p>
          )}
          {voices.length === 0 && !loadError && (
            <p className="text-xs text-gray-500">No bundled voices found.</p>
          )}
          <div className="space-y-2">
            {voices.map((voice) => {
              const selected = highlightCfg.voice_id === voice.id;
              return (
                <div
                  key={voice.id}
                  className={`flex items-center gap-3 rounded-lg border p-3 transition ${
                    selected
                      ? "border-indigo-500 bg-indigo-50"
                      : "border-gray-200 hover:border-gray-300"
                  } ${!voice.available ? "opacity-50" : ""}`}
                >
                  <button
                    type="button"
                    disabled={!voice.available}
                    onClick={() => voice.available && handleVoiceSelect(voice)}
                    className="flex-1 text-left disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900">
                        {voice.name}
                      </span>
                      <span className="text-[10px] uppercase tracking-wide text-gray-500 px-1.5 py-0.5 rounded bg-gray-100">
                        {voice.language}
                      </span>
                      {!voice.available && (
                        <span className="text-[10px] text-amber-700">
                          (audio missing)
                        </span>
                      )}
                    </div>
                    {voice.description && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {voice.description}
                      </p>
                    )}
                  </button>
                  {voice.available && (
                    <audio
                      controls
                      preload="none"
                      src={voiceAudioUrl(voice.id)}
                      className="h-8"
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Upload custom reference */}
      {voiceSource === "upload" && (
        <div className="space-y-2">
          {uploadedRefName ? (
            <p className="text-sm text-green-700">{uploadedRefName}</p>
          ) : (
            <FileUploader
              accept="audio/*"
              label="Upload a reference audio clip (10–20s, mono)"
              onUploaded={(f: UploadedFile) => {
                setUploadedRefName(f.original_name);
                onChange({
                  ref_audio_file_id: f.id,
                  voice_id: null,
                });
              }}
            />
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reference transcript (optional)
            </label>
            <textarea
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              rows={2}
              placeholder="Exact words spoken in the reference clip…"
              value={highlightCfg.ref_text || ""}
              onChange={(e) =>
                onChange({ ref_text: e.target.value || null })
              }
            />
          </div>
        </div>
      )}

      {/* Language */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Language
        </label>
        <select
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={config.language}
          onChange={(e) => onChange({ language: e.target.value })}
        >
          {languages.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-500">
          Languages supported by Qwen3-TTS.
        </p>
      </div>

      {/* Sample preview */}
      <div className="rounded-lg border border-dashed border-gray-300 p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-gray-800">Preview sample</p>
            <p className="text-xs text-gray-500">
              Generate a short clip with this voice + language before processing the whole document.
            </p>
          </div>
          <button
            type="button"
            onClick={handleGenerateSample}
            disabled={!canPreview}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
              canPreview
                ? "bg-indigo-600 text-white hover:bg-indigo-700"
                : "bg-gray-200 text-gray-500 cursor-not-allowed"
            }`}
          >
            {previewLoading ? "Generating…" : "Generate sample"}
          </button>
        </div>
        {previewError && (
          <p className="mt-2 text-xs text-red-600">{previewError}</p>
        )}
        {previewUrl && (
          <audio controls src={previewUrl} className="mt-2 w-full" />
        )}
      </div>
    </div>
  );
}
