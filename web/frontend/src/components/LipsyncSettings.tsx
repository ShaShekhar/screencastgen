import { useState } from "react";
import FileUploader from "./FileUploader";
import { LipsyncConfig, UploadedFile } from "../types";

interface Props {
  config: LipsyncConfig;
  onChange: (c: LipsyncConfig) => void;
}

const FACE_POSITIONS = ["left", "right", "center"];
const ALIGNERS = [
  { value: "whisperx", label: "WhisperX" },
];
const LIPSYNC_PROVIDERS = [
  { value: "auto", label: "Auto" },
  { value: "latentsync", label: "LatentSync" },
  { value: "wav2lip", label: "Wav2Lip" },
];

export default function LipsyncSettings({ config, onChange }: Props) {
  const [audioName, setAudioName] = useState<string | null>(null);
  const [videoName, setVideoName] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Reference Audio (voice to clone)
        </label>
        {audioName ? (
          <p className="text-sm text-green-700">{audioName}</p>
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
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Reference Video (face, ~10 seconds)
        </label>
        {videoName ? (
          <p className="text-sm text-green-700">{videoName}</p>
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
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Reference Text (optional, auto-transcribed if empty)
        </label>
        <textarea
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          rows={3}
          placeholder="Transcript of reference audio..."
          value={config.ref_text || ""}
          onChange={(e) =>
            onChange({ ...config, ref_text: e.target.value || undefined })
          }
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Face Position
        </label>
        <div className="flex gap-3">
          {FACE_POSITIONS.map((pos) => (
            <label key={pos} className="flex items-center gap-1.5 text-sm capitalize">
              <input
                type="radio"
                name="face_position"
                value={pos}
                checked={config.face_position === pos}
                onChange={() => onChange({ ...config, face_position: pos })}
              />
              {pos}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Aligner
        </label>
        <select
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={config.aligner || "whisperx"}
          onChange={(e) => onChange({ ...config, aligner: e.target.value })}
        >
          {ALIGNERS.map((aligner) => (
            <option key={aligner.value} value={aligner.value}>
              {aligner.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Lip-Sync Provider
        </label>
        <select
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={config.lipsync_provider || "auto"}
          onChange={(e) =>
            onChange({ ...config, lipsync_provider: e.target.value })
          }
        >
          {LIPSYNC_PROVIDERS.map((provider) => (
            <option key={provider.value} value={provider.value}>
              {provider.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Device
        </label>
        <select
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={config.device}
          onChange={(e) => onChange({ ...config, device: e.target.value })}
        >
          <option value="auto">Auto</option>
          <option value="cuda">CUDA (GPU)</option>
          <option value="cpu">CPU</option>
        </select>
      </div>
    </div>
  );
}
