import { AudioConfig } from "../types";

interface Props {
  config: AudioConfig;
  onChange: (c: AudioConfig) => void;
}

const VOICES = [
  "en-US-Chirp3-HD-Algenib",
  "en-US-Chirp3-HD-Aoede",
  "en-GB-Chirp3-HD-Aoede",
  "en-US-Chirp3-HD-Puck",
  "en-US-Chirp3-HD-Kore",
];

const ENCODINGS = ["MP3", "LINEAR16", "OGG_OPUS"];

export default function VoiceSettings({ config, onChange }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Voice
        </label>
        <select
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={config.voice}
          onChange={(e) => onChange({ ...config, voice: e.target.value })}
        >
          {VOICES.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </div>

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

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Encoding
        </label>
        <div className="flex gap-3">
          {ENCODINGS.map((enc) => (
            <label key={enc} className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                name="encoding"
                value={enc}
                checked={config.encoding === enc}
                onChange={() => onChange({ ...config, encoding: enc })}
              />
              {enc}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
