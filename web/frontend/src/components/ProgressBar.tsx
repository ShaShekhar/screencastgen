import { JobStatus } from "../types";

interface Props {
  current: number;
  total: number;
  phase: string;
  status: JobStatus;
}

export default function ProgressBar({ current, total, phase, status }: Props) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;

  const barColor =
    status === "completed"
      ? "bg-green-500"
      : status === "failed"
      ? "bg-red-500"
      : "bg-indigo-600";

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600 capitalize">{phase}</span>
        <span className="text-gray-500">
          {total > 0 ? `${current}/${total}` : ""} {pct > 0 ? `(${pct}%)` : ""}
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className={`h-3 rounded-full transition-all duration-500 ${barColor} ${
            status === "running" ? "animate-pulse" : ""
          }`}
          style={{ width: `${Math.max(pct, status === "running" ? 2 : 0)}%` }}
        />
      </div>
    </div>
  );
}
