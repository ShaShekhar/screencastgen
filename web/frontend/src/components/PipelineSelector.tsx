import { PipelineType } from "../types";

interface Props {
  selected: PipelineType;
  onChange: (t: PipelineType) => void;
}

const PIPELINES: { type: PipelineType; title: string; desc: string }[] = [
  {
    type: "lipsync",
    title: "Talking-Head Reader",
    desc: "Synchronized document, narration, and lip-synced presenter",
  },
  {
    type: "highlight",
    title: "Read-Along EPUB",
    desc: "Secondary accessibility export with synchronized text and narration",
  },
  {
    type: "visualization",
    title: "Concept Visualization",
    desc: "Prompt-driven math animation rendered as a standalone MP4",
  },
];

export default function PipelineSelector({ selected, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
