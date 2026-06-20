import { useEffect, useMemo, useRef, useState } from "react";
import { stopJob } from "../api/jobs";
import type { LipsyncPageTime, ProgressEvent } from "../types";

interface Props {
  jobId: string;
  progress: ProgressEvent | null;
  initialPageTimes?: LipsyncPageTime[];
}

function fmtDuration(secs: number): string {
  const s = Math.max(0, Math.round(secs));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}m ${r.toString().padStart(2, "0")}s` : `${r}s`;
}

/**
 * Live status for a running lip-sync job: per-page generation times, a ticking
 * timer for the page currently on the GPU, and a Stop control. Lip-sync pages
 * each take minutes, so this lets the user judge how long a run will take and
 * stop whenever they have enough pages.
 */
export default function LipsyncRunPanel({
  jobId,
  progress,
  initialPageTimes,
}: Props) {
  const [pageTimes, setPageTimes] = useState<LipsyncPageTime[]>(
    initialPageTimes ?? [],
  );
  const [totalPages, setTotalPages] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [stopping, setStopping] = useState(false);
  const [showStopConfirm, setShowStopConfirm] = useState(false);
  const [stopError, setStopError] = useState<string | null>(null);
  const pageStartRef = useRef<number | null>(null);

  useEffect(() => {
    const data = progress?.data;
    if (!data) return;
    if (typeof data.total === "number" && data.total > 0) {
      setTotalPages(data.total);
    }
    if (data.event === "page_done") {
      if (data.page_times) setPageTimes(data.page_times);
      setCurrentPage(null);
      pageStartRef.current = null;
    } else if (data.event === "page_start") {
      setCurrentPage(data.page);
      pageStartRef.current = Date.now();
    } else if (data.event === "page_progress") {
      // Recover the current page if the page_start event was missed.
      setCurrentPage((prev) => (prev == null ? data.page : prev));
      if (pageStartRef.current == null) {
        pageStartRef.current = Date.now() - (data.elapsed ?? 0) * 1000;
      }
    }
  }, [progress]);

  // Tick once a second only while a page is actively generating.
  useEffect(() => {
    if (currentPage == null) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [currentPage]);

  const handleStop = async () => {
    setStopping(true);
    setStopError(null);
    try {
      await stopJob(jobId);
      setShowStopConfirm(false);
    } catch {
      setStopping(false);
      setStopError("Could not send the stop request — try again.");
    }
  };

  const currentElapsed =
    currentPage != null && pageStartRef.current != null
      ? (now - pageStartRef.current) / 1000
      : 0;

  const totalSpent = useMemo(
    () => pageTimes.reduce((sum, p) => sum + p.seconds, 0) + currentElapsed,
    [pageTimes, currentElapsed],
  );

  const completed = pageTimes.length;

  return (
    <div className="mt-4 border-t border-gray-200 pt-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-sm font-semibold text-gray-700">
          Lip-Sync Generation
        </h3>
        <span className="text-xs text-gray-500">
          {completed} {totalPages ? `of ${totalPages} ` : ""}
          page{completed === 1 ? "" : "s"} done · {fmtDuration(totalSpent)} total
        </span>
      </div>

      {(completed > 0 || currentPage != null) && (
        <ul className="space-y-1 mb-3">
          {pageTimes.map((p) => (
            <li
              key={p.page}
              className="flex items-center justify-between text-sm text-gray-600"
            >
              <span>Page {p.page}</span>
              <span className="tabular-nums text-gray-500">
                ✓ {fmtDuration(p.seconds)}
              </span>
            </li>
          ))}
          {currentPage != null && (
            <li className="flex items-center justify-between text-sm text-blue-700">
              <span>Page {currentPage}</span>
              <span className="tabular-nums">
                ⏳ generating… {fmtDuration(currentElapsed)}
              </span>
            </li>
          )}
        </ul>
      )}

      <p className="text-xs text-gray-500 mb-3">
        Generation runs without a timeout. Stop whenever you have enough pages —
        the video is built from the pages already completed.
      </p>

      {showStopConfirm ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="mb-3 text-sm text-amber-800">
            Stop this job? The page currently generating may be discarded. The
            final video will include only the pages already completed.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleStop}
              disabled={stopping}
              className="rounded-lg bg-amber-600 px-4 py-2 text-sm text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {stopping ? "Stopping…" : "Yes, stop and build"}
            </button>
            <button
              type="button"
              onClick={() => setShowStopConfirm(false)}
              disabled={stopping}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Keep running
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => {
            setStopError(null);
            setShowStopConfirm(true);
          }}
          disabled={stopping}
          className={`px-4 py-2 text-sm rounded-lg border transition ${
            stopping
              ? "border-gray-200 text-gray-400 cursor-not-allowed"
              : "border-amber-300 text-amber-700 hover:bg-amber-50"
          }`}
        >
          {stopping ? "Stopping…" : "Stop & build from completed pages"}
        </button>
      )}

      {stopError && <p className="mt-2 text-sm text-red-600">{stopError}</p>}
    </div>
  );
}
