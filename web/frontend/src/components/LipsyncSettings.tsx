import { useEffect, useState } from "react";
import {
  lipsyncPresetAudioUrl,
  lipsyncPresetVideoUrl,
  listLipsyncPresets,
} from "../api/lipsyncPresets";
import FileUploader from "./FileUploader";
import type { LipsyncConfig, LipsyncPreset, UploadedFile } from "../types";

interface Props {
  config: LipsyncConfig;
  onChange: (c: LipsyncConfig) => void;
}

type ReferenceSource = "bundled" | "upload";

export const FACE_POSITIONS = [
  { value: "bottom-right", label: "Bottom Right" },
  { value: "top-right", label: "Top Right" },
  { value: "bottom-left", label: "Bottom Left" },
  { value: "top-left", label: "Top Left" },
  { value: "left", label: "Split Left" },
  { value: "right", label: "Split Right" },
  { value: "center", label: "Top Center" },
];
const LATENTSYNC_PRESETS = [
  { value: "small", label: "256 Fast" },
  { value: "balanced_256", label: "256 Balanced" },
  { value: "quality", label: "512 High Quality" },
];

export default function LipsyncSettings({ config, onChange }: Props) {
  const [audioName, setAudioName] = useState<string | null>(null);
  const [videoName, setVideoName] = useState<string | null>(null);
  const [presets, setPresets] = useState<LipsyncPreset[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [source, setSource] = useState<ReferenceSource>(
    config.ref_video_file_id ? "upload" : "bundled",
  );

  const availablePresets = presets.filter((preset) => preset.available);
  const selectedPreset = presets.find((preset) => preset.id === config.preset_id);

  useEffect(() => {
    let cancelled = false;
    listLipsyncPresets()
      .then((items) => {
        if (!cancelled) setPresets(items);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setLoadError(
            e instanceof Error ? e.message : "Failed to load presenter presets",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (
      source === "bundled" &&
      !config.preset_id &&
      !config.ref_video_file_id &&
      availablePresets.length > 0
    ) {
      onChange({
        ...config,
        preset_id: availablePresets[0].id,
        ref_audio_file_id: null,
        ref_video_file_id: null,
      });
    }
  }, [availablePresets, config, onChange, source]);

  const resetVideo = () => {
    setVideoName(null);
    onChange({ ...config, ref_video_file_id: null });
  };

  const resetAudio = () => {
    setAudioName(null);
    onChange({ ...config, ref_audio_file_id: null });
  };

  const handleSourceChange = (nextSource: ReferenceSource) => {
    setSource(nextSource);
    setAudioName(null);
    setVideoName(null);
    if (nextSource === "bundled") {
      onChange({
        ...config,
        preset_id: availablePresets[0]?.id || null,
        ref_audio_file_id: null,
        ref_video_file_id: null,
      });
    } else {
      onChange({
        ...config,
        preset_id: null,
        ref_audio_file_id: null,
        ref_video_file_id: null,
      });
    }
  };

  const handlePresetSelect = (preset: LipsyncPreset) => {
    if (!preset.available) return;
    setAudioName(null);
    setVideoName(null);
    onChange({
      ...config,
      preset_id: preset.id,
      ref_audio_file_id: null,
      ref_video_file_id: null,
    });
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Presenter Reference
        </label>
        <div className="inline-flex rounded-lg bg-gray-100 p-1">
          <button
            type="button"
            onClick={() => handleSourceChange("bundled")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition ${
              source === "bundled"
                ? "bg-white text-indigo-700 shadow-sm"
                : "text-gray-500"
            }`}
          >
            Bundled
          </button>
          <button
            type="button"
            onClick={() => handleSourceChange("upload")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition ${
              source === "upload"
                ? "bg-white text-indigo-700 shadow-sm"
                : "text-gray-500"
            }`}
          >
            Upload
          </button>
        </div>
      </div>

      {source === "bundled" && (
        <div className="space-y-3">
          {loadError && <p className="text-xs text-red-600">{loadError}</p>}
          {presets.length === 0 && !loadError && (
            <p className="text-xs text-gray-500">No bundled presenter presets found.</p>
          )}
          {presets.map((preset) => {
            const selected = config.preset_id === preset.id;
            return (
              <div
                key={preset.id}
                className={`rounded-lg border p-3 transition ${
                  selected
                    ? "border-indigo-300 bg-indigo-50"
                    : "border-gray-200 bg-white"
                } ${!preset.available ? "opacity-50" : ""}`}
              >
                <div className="flex items-start gap-3">
                  {preset.available && (
                    <video
                      src={lipsyncPresetVideoUrl(preset.id)}
                      className="h-20 w-28 shrink-0 rounded-md bg-black object-cover"
                      muted
                      playsInline
                      controls
                    />
                  )}
                  <button
                    type="button"
                    disabled={!preset.available}
                    onClick={() => handlePresetSelect(preset)}
                    className="min-w-0 flex-1 text-left disabled:cursor-not-allowed"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900">
                        {preset.name}
                      </span>
                      <span className="text-[10px] uppercase tracking-wide text-gray-500 px-1.5 py-0.5 rounded bg-gray-100">
                        {preset.language}
                      </span>
                      {!preset.available && (
                        <span className="text-[10px] text-amber-700">
                          Missing files
                        </span>
                      )}
                    </div>
                    {preset.description && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {preset.description}
                      </p>
                    )}
                  </button>
                </div>
                {preset.available && preset.has_audio && (
                  <audio
                    className="mt-3 w-full h-8"
                    src={lipsyncPresetAudioUrl(preset.id)}
                    controls
                  />
                )}
              </div>
            );
          })}
          {selectedPreset && (
            <p className="text-xs text-gray-500">
              Bundled presets use the presenter's own video audio unless the preset includes a separate audio override.
            </p>
          )}
        </div>
      )}

      {source === "upload" && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reference Video (face and voice, about 10 seconds)
            </label>
            {videoName ? (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2">
                <p className="min-w-0 truncate text-sm font-medium text-green-700">
                  {videoName}
                </p>
                <button
                  type="button"
                  onClick={resetVideo}
                  className="shrink-0 rounded-md border border-green-300 px-2.5 py-1 text-xs font-medium text-green-700 hover:bg-green-100 transition"
                >
                  Replace
                </button>
              </div>
            ) : (
              <FileUploader
                accept="video/*,.mp4,.mov,.m4v,.webm,.ogg,.ogv"
                label="Upload reference face video"
                onUploaded={(f: UploadedFile) => {
                  setVideoName(f.original_name);
                  onChange({
                    ...config,
                    preset_id: null,
                    ref_video_file_id: f.id,
                  });
                }}
              />
            )}
            <p className="mt-1 text-xs text-gray-500">
              If this video has clear speaker audio, the generated narration will clone that same voice.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reference Audio Override (optional)
            </label>
            {audioName ? (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2">
                <p className="min-w-0 truncate text-sm font-medium text-green-700">
                  {audioName}
                </p>
                <button
                  type="button"
                  onClick={resetAudio}
                  className="shrink-0 rounded-md border border-green-300 px-2.5 py-1 text-xs font-medium text-green-700 hover:bg-green-100 transition"
                >
                  Replace
                </button>
              </div>
            ) : (
              <FileUploader
                accept="audio/*,.wav,.mp3,.m4a,.aac,.flac,.ogg"
                label="Upload reference audio clip"
                onUploaded={(f: UploadedFile) => {
                  setAudioName(f.original_name);
                  onChange({
                    ...config,
                    preset_id: null,
                    ref_audio_file_id: f.id,
                  });
                }}
              />
            )}
            <p className="mt-1 text-xs text-gray-500">
              Upload audio only when you want to override the voice embedded in the reference video.
            </p>
          </div>
        </>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Face Position
        </label>
        <select
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={config.face_position}
          onChange={(e) =>
            onChange({ ...config, face_position: e.target.value })
          }
        >
          {FACE_POSITIONS.map((pos) => (
            <option key={pos.value} value={pos.value}>
              {pos.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          LatentSync Preset
        </label>
        <select
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={config.latentsync_preset}
          onChange={(e) =>
            onChange({ ...config, latentsync_preset: e.target.value })
          }
        >
          {LATENTSYNC_PRESETS.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-500">
          256 Balanced uses guidance 1.5 and 30 inference steps. 512 High Quality uses the 512 pipeline.
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Presenter Scale
        </label>
        <input
          type="range"
          min={0.12}
          max={0.4}
          step={0.01}
          value={config.face_scale}
          onChange={(e) =>
            onChange({ ...config, face_scale: Number(e.target.value) })
          }
          className="w-full"
        />
        <p className="mt-1 text-xs text-gray-500">
          {Math.round(config.face_scale * 100)}% of frame width for docked corner layouts.
        </p>
      </div>
    </div>
  );
}
