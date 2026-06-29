import { Link } from "react-router-dom";
import { type ReactNode } from "react";
import { Job } from "../types";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const PIPELINE_LABELS: Record<string, string> = {
  audio: "Audio",
  highlight: "Audio Reader",
  lipsync: "Lip-Sync Video Reader",
  visualization: "Concept Visualization",
};

export default function JobCard({ job }: { job: Job }) {
  const pct =
    job.progress_total > 0
      ? Math.round((job.progress_current / job.progress_total) * 100)
      : 0;
  const opensReader =
    job.status === "completed" &&
    (job.pipeline_type === "highlight" || job.pipeline_type === "lipsync");
  const href = `/jobs/${job.id}/read`;
  const className =
    "block bg-white rounded-xl border border-gray-200 p-5 transition " +
    (opensReader ? "hover:shadow-md" : "");
  const content: ReactNode = (
    <>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-500">
          {PIPELINE_LABELS[job.pipeline_type] || job.pipeline_type}
        </span>
        <span
          className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${
            STATUS_STYLES[job.status] || ""
          }`}
        >
          {job.status}
        </span>
      </div>

      <p className="text-sm text-gray-700 truncate mb-2">
        {job.pipeline_type === "visualization" && typeof job.config_json.prompt === "string"
          ? job.config_json.prompt
          : `Job ${job.id.slice(0, 8)}...`}
      </p>

      {job.status === "running" && (
        <div className="w-full bg-gray-200 rounded-full h-1.5 mt-2">
          <div
            className="bg-indigo-600 h-1.5 rounded-full transition-all animate-pulse"
            style={{ width: `${Math.max(pct, 2)}%` }}
          />
        </div>
      )}

      <p className="text-xs text-gray-400 mt-2">
        {new Date(job.created_at).toLocaleString()}
      </p>
    </>
  );

  if (!opensReader) {
    return <div className={className}>{content}</div>;
  }

  return (
    <Link
      to={href}
      className={className}
    >
      {content}
    </Link>
  );
}
