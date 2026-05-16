import { useState } from "react";
import FileUploader from "./FileUploader";
import { LipsyncConfig, UploadedFile } from "../types";

interface Props {
  config: LipsyncConfig;
  onChange: (c: LipsyncConfig) => void;
}

const FACE_POSITIONS = [
  { value: "bottom-right", label: "Bottom Right" },
  { value: "top-right", label: "Top Right" },
  { value: "bottom-left", label: "Bottom Left" },
  { value: "top-left", label: "Top Left" },
  { value: "left", label: "Split Left" },
  { value: "right", label: "Split Right" },
  { value: "center", label: "Top Center" },
];
const LATENTSYNC_PRESETS = [
  { value: "small", label: "Small Docked (Recommended)" },
  { value: "quality", label: "Higher Quality" },
];

export default function LipsyncSettings({ config, onChange }: Props) {
  const [audioName, setAudioName] = useState<string | null>(null);
  const [videoName, setVideoName] = useState<string | null>(null);

  const resetVideo = () => {
    setVideoName(null);
    onChange({ ...config, ref_video_file_id: "" });
  };

  const resetAudio = () => {
    setAudioName(null);
    onChange({ ...config, ref_audio_file_id: null });
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Reference Video (face and voice, ~10 seconds)
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
            accept="video/*"
            label="Upload reference face video"
            onUploaded={(f: UploadedFile) => {
              setVideoName(f.original_name);
              onChange({ ...config, ref_video_file_id: f.id });
            }}
          />
        )}
        <p className="mt-1 text-xs text-gray-500">
          If this video has clear speaker audio, it will be used as the voice reference.
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
            accept="audio/*"
            label="Upload reference audio clip"
            onUploaded={(f: UploadedFile) => {
              setAudioName(f.original_name);
              onChange({ ...config, ref_audio_file_id: f.id });
            }}
          />
        )}
        <p className="mt-1 text-xs text-gray-500">
          Upload audio only when you want to override the audio embedded in the reference video.
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Face Position
        </label>
        <div className="grid grid-cols-2 gap-2">
          {FACE_POSITIONS.map((pos) => (
            <label key={pos.value} className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                name="face_position"
                value={pos.value}
                checked={config.face_position === pos.value}
                onChange={() => onChange({ ...config, face_position: pos.value })}
              />
              {pos.label}
            </label>
          ))}
        </div>
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
          Use `small` for corner-docked presenter videos. `quality` keeps the 512 pipeline.
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
