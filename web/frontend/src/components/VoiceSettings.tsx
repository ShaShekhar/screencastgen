import { AudioConfig } from "../types";

interface Props {
  config: AudioConfig;
  onChange: (c: AudioConfig) => void;
  showAligner?: boolean;
}

const ALIGNERS = [
  { value: "whisperx", label: "WhisperX" },
];

export default function VoiceSettings({
  config,
  onChange,
  showAligner = false,
}: Props) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Language
        </label>
        <input
          type="text"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={config.language}
          onChange={(e) => onChange({ ...config, language: e.target.value })}
        />
      </div>

      {showAligner && (
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
      )}
    </div>
  );
}
