import { PipelineType } from "../types";

interface Props {
  selected: PipelineType;
  onChange: (t: PipelineType) => void;
}

const PIPELINES: { type: PipelineType; title: string; desc: string }[] = [
  {
    type: "highlight",
    title: "Highlight Text Audio",
    desc: "Audiobook-style narration with synced word-by-word highlighted text video",
  },
  {
    type: "lipsync",
    title: "Lip-Sync Video",
    desc: "Voice-cloned audio with a lip-synced talking head overlay",
  },
];

export default function PipelineSelector({ selected, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {PIPELINES.map((p) => (
        <button
          key={p.type}
          type="button"
          onClick={() => onChange(p.type)}
          className={`p-4 rounded-xl border-2 text-left transition ${
            selected === p.type
              ? "border-indigo-600 bg-indigo-50"
              : "border-gray-200 hover:border-gray-300"
          }`}
        >
          <h3 className="font-semibold text-sm mb-1">{p.title}</h3>
          <p className="text-xs text-gray-500">{p.desc}</p>
        </button>
      ))}
    </div>
  );
}
