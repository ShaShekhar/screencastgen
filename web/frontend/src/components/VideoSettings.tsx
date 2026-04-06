interface VideoConfig {
  font_size: number;
  width: number;
  height: number;
  fps: number;
}

interface Props {
  config: VideoConfig;
  onChange: (c: VideoConfig) => void;
}

const RESOLUTIONS = [
  { label: "1280x720 (HD)", w: 1280, h: 720 },
  { label: "1920x1080 (Full HD)", w: 1920, h: 1080 },
  { label: "854x480 (SD)", w: 854, h: 480 },
];

export default function VideoSettings({ config, onChange }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Resolution
        </label>
        <select
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={`${config.width}x${config.height}`}
          onChange={(e) => {
            const r = RESOLUTIONS.find(
              (r) => `${r.w}x${r.h}` === e.target.value
            );
            if (r) onChange({ ...config, width: r.w, height: r.h });
          }}
        >
          {RESOLUTIONS.map((r) => (
            <option key={`${r.w}x${r.h}`} value={`${r.w}x${r.h}`}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            FPS
          </label>
          <input
            type="number"
            min={1}
            max={60}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            value={config.fps}
            onChange={(e) =>
              onChange({ ...config, fps: parseInt(e.target.value) || 24 })
            }
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Font Size
          </label>
          <input
            type="number"
            min={12}
            max={72}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            value={config.font_size}
            onChange={(e) =>
              onChange({
                ...config,
                font_size: parseInt(e.target.value) || 32,
              })
            }
          />
        </div>
      </div>
    </div>
  );
}
