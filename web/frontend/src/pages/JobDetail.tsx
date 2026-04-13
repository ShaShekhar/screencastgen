import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteJob, getDownloadUrl, getJob } from "../api/jobs";
import { getReaderStatus } from "../api/reader";
import ProgressBar from "../components/ProgressBar";
import { useJobProgress } from "../hooks/useJobProgress";
import { Job, JobStatus } from "../types";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const PIPELINE_LABELS: Record<string, string> = {
  audio: "Audio",
  highlight: "Highlight Text Audio",
  lipsync: "Lip-Sync Video",
};

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [readerReady, setReaderReady] = useState<boolean | null>(null);
  const [readerMessage, setReaderMessage] = useState<string | null>(null);

  const isActive = job?.status === "pending" || job?.status === "running";
  const progress = useJobProgress(id, isActive ?? false);

  const fetchJob = useCallback(async () => {
    if (!id) return;
    try {
      const j = await getJob(id);
      setJob(j);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  useEffect(() => {
    if (!id || !job) return;
    if (job.pipeline_type !== "highlight" || job.status !== "completed") {
      setReaderReady(null);
      setReaderMessage(null);
      return;
    }

    let cancelled = false;
    setReaderReady(null);
    setReaderMessage("Checking browser reader...");

    getReaderStatus(id)
      .then((status) => {
        if (cancelled) return;
        setReaderReady(status.available);
        setReaderMessage(status.message);
      })
      .catch(() => {
        if (cancelled) return;
        setReaderReady(false);
        setReaderMessage("Could not verify browser reader availability.");
      });

    return () => {
      cancelled = true;
    };
  }, [id, job]);

  // Update job from SSE progress
  useEffect(() => {
    if (!progress || !job) return;
    setJob((prev) =>
      prev
        ? {
            ...prev,
            status: progress.status as JobStatus,
            progress_current: progress.current,
            progress_total: progress.total,
            progress_phase: progress.phase,
          }
        : prev
    );
    // Re-fetch on terminal status for full data
    if (progress.status === "completed" || progress.status === "failed") {
      fetchJob();
    }
  }, [progress, fetchJob]);

  const handleDelete = async () => {
    if (!id) return;
    setDeleting(true);
    try {
      await deleteJob(id);
      navigate("/");
    } catch {
      setDeleting(false);
    }
  };

  if (loading) {
    return <p className="text-gray-500 text-sm">Loading...</p>;
  }

  if (!job) {
    return <p className="text-red-600">Job not found</p>;
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Job Detail</h1>
          <p className="text-sm text-gray-500 mt-1 font-mono">{job.id}</p>
        </div>
        <span
          className={`text-sm font-semibold px-3 py-1 rounded-full ${
            STATUS_STYLES[job.status] || ""
          }`}
        >
          {job.status}
        </span>
      </div>

      {/* Info */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Pipeline</span>
            <p className="font-medium">
              {PIPELINE_LABELS[job.pipeline_type] || job.pipeline_type}
            </p>
          </div>
          <div>
            <span className="text-gray-500">Created</span>
            <p className="font-medium">
              {new Date(job.created_at).toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Progress */}
      {(job.status === "running" || job.status === "pending") && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">
            Progress
          </h2>
          <ProgressBar
            current={job.progress_current}
            total={job.progress_total}
            phase={job.progress_phase}
            status={job.status}
          />
        </div>
      )}

      {/* Completed */}
      {job.status === "completed" && job.output_path && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-green-800 mb-3">
            Output Ready
          </h2>
          <p className="text-sm text-green-700 mb-3">{job.output_path}</p>
          <div className="flex flex-wrap gap-3">
            <a
              href={getDownloadUrl(job.id)}
              className="inline-block bg-green-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-green-700 transition"
            >
              Download
            </a>
            {job.pipeline_type === "highlight" && readerReady && (
              <Link
                to={`/jobs/${job.id}/read`}
                className="inline-block bg-white text-green-700 border border-green-300 px-5 py-2 rounded-lg text-sm font-medium hover:bg-green-100 transition"
              >
                Open Reader
              </Link>
            )}
          </div>
          {job.pipeline_type === "highlight" && readerMessage && (
            <p
              className={`mt-3 text-sm ${
                readerReady === false
                  ? "text-amber-700"
                  : readerReady === true
                    ? "text-green-700"
                    : "text-gray-600"
              }`}
            >
              {readerMessage}
            </p>
          )}
        </div>
      )}

      {/* Failed */}
      {job.status === "failed" && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-red-800 mb-2">
            Job Failed
          </h2>
          <p className="text-sm text-red-700 font-mono whitespace-pre-wrap">
            {job.error_message || "Unknown error"}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={() => navigate("/")}
          className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition"
        >
          Back to Jobs
        </button>
        {showConfirm ? (
          <div className="flex gap-2">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
            >
              {deleting ? "Deleting..." : "Confirm Delete"}
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowConfirm(true)}
            className="px-4 py-2 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition"
          >
            Delete Job
          </button>
        )}
      </div>
    </div>
  );
}
