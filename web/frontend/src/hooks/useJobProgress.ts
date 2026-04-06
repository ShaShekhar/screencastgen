import { useEffect, useRef, useState } from "react";
import { ProgressEvent } from "../types";

export function useJobProgress(jobId: string | undefined, enabled: boolean) {
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId || !enabled) return;

    const es = new EventSource(`/api/jobs/${jobId}/events`);
    esRef.current = es;

    es.addEventListener("progress", (e: MessageEvent) => {
      try {
        setProgress(JSON.parse(e.data));
      } catch {
        // ignore
      }
    });

    es.addEventListener("done", (e: MessageEvent) => {
      try {
        setProgress(JSON.parse(e.data));
      } catch {
        // ignore
      }
      es.close();
    });

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [jobId, enabled]);

  return progress;
}
