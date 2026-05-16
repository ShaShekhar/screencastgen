import {
  ChangeEvent,
  CSSProperties,
  PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useParams } from "react-router-dom";
import {
  getReaderAudioUrl,
  getReaderManifest,
  getReaderPageUrl,
  getReaderPresenterUrl,
} from "../api/reader";
import {
  getDownloadUrl,
  getMp4ExportDownloadUrl,
  getMp4ExportStatus,
  requestMp4Export,
} from "../api/jobs";
import { Mp4ExportStatus, ReaderChunk, ReaderManifest } from "../types";

interface FlatWord {
  word: string;
  start: number;
  end: number;
  page: number;
}

type ThemeName = "night" | "pdf";

interface ThemeColors {
  bg: string;
  fg: string;
  surface: string;
  border: string;
  muted: string;
  highlightBg: string;
  highlightFg: string;
  hover: string;
}

const THEMES: Record<ThemeName, ThemeColors> = {
  night: {
    bg: "#0b0b0c",
    fg: "#e8e8ea",
    surface: "#18181b",
    border: "#2e2e33",
    muted: "#9a9aa2",
    highlightBg: "#facc15",
    highlightFg: "#0b0b0c",
    hover: "#27272a",
  },
  pdf: {
    bg: "#f7f1e3",
    fg: "#1f2937",
    surface: "#fffaf0",
    border: "#e8dcc2",
    muted: "#8d7751",
    highlightBg: "#fcd34d",
    highlightFg: "#1f2937",
    hover: "#fdf0d0",
  },
};

const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 1.75, 2];
const PIP_MIN_W = 160;
const PIP_MAX_W = 640;
const PIP_DEFAULT_W = 280;
const PIP_EDGE = 16; // px-wide hit zone along each edge for resizing
const THEME_KEY = "reader-theme";
const PIP_POS_KEY = "reader-pip-pos";
const PIP_WIDTH_KEY = "reader-pip-width";

type PipZone = "e" | "s" | "se" | "drag";

const ZONE_CURSOR: Record<PipZone, string> = {
  e: "ew-resize",
  s: "ns-resize",
  se: "nwse-resize",
  drag: "grab",
};

/** Classify a pointer position over the PiP as a resize edge or a drag. */
function pipZoneAt(el: HTMLElement, clientX: number, clientY: number): PipZone {
  const r = el.getBoundingClientRect();
  const onRight = clientX >= r.right - PIP_EDGE;
  const onBottom = clientY >= r.bottom - PIP_EDGE;
  if (onRight && onBottom) return "se";
  if (onRight) return "e";
  if (onBottom) return "s";
  return "drag";
}

function fmtTime(secs: number): string {
  if (!Number.isFinite(secs) || secs < 0) return "0:00";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function findActiveWordIndex(words: FlatWord[], t: number): number {
  if (words.length === 0) return -1;
  let lo = 0;
  let hi = words.length - 1;
  let best = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const w = words[mid];
    if (t < w.start) {
      hi = mid - 1;
    } else if (t > w.end) {
      best = mid;
      lo = mid + 1;
    } else {
      return mid;
    }
  }
  return best;
}

function loadTheme(): ThemeName {
  const stored = localStorage.getItem(THEME_KEY);
  return stored === "pdf" ? "pdf" : "night";
}

export default function Reader() {
  const { id } = useParams<{ id: string }>();
  const [manifest, setManifest] = useState<ReaderManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [hasStartedPlaying, setHasStartedPlaying] = useState(false);

  const [theme, setTheme] = useState<ThemeName>(loadTheme);
  const [invertPages, setInvertPages] = useState(false);
  const [pipWidth, setPipWidth] = useState<number>(() => {
    const stored = Number(localStorage.getItem(PIP_WIDTH_KEY));
    return Number.isFinite(stored) && stored >= PIP_MIN_W && stored <= PIP_MAX_W
      ? stored
      : PIP_DEFAULT_W;
  });
  const [pipCursor, setPipCursor] = useState("grab");
  const [pipVisible, setPipVisible] = useState(true);
  const [exportStatus, setExportStatus] = useState<Mp4ExportStatus>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [pipPos, setPipPos] = useState<{ x: number; y: number }>(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(PIP_POS_KEY) || "");
      if (stored && typeof stored.x === "number" && typeof stored.y === "number") {
        return stored;
      }
    } catch {
      /* ignore */
    }
    return { x: 24, y: 80 };
  });

  const mediaRef = useRef<HTMLMediaElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const scrollerRef = useRef<HTMLElement | null>(null);
  const scrollTargetRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasStartedPlayingRef = useRef(false);
  const pipGestureRef = useRef<
    | { type: "drag"; dx: number; dy: number }
    | {
        type: "resize";
        mode: "e" | "s" | "se";
        startW: number;
        startX: number;
        startY: number;
        aspect: number;
      }
    | null
  >(null);

  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(PIP_WIDTH_KEY, String(Math.round(pipWidth)));
  }, [pipWidth]);

  useEffect(() => {
    localStorage.setItem(PIP_POS_KEY, JSON.stringify(pipPos));
  }, [pipPos]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setManifest(null);
    setError(null);
    setActiveIdx(-1);
    setCurrentTime(0);

    getReaderManifest(id)
      .then((nextManifest) => {
        if (!cancelled) setManifest(nextManifest);
      })
      .catch((err) => {
        if (!cancelled) {
          const msg =
            err?.response?.status === 404
              ? "This job does not have a browser reader available."
              : "Failed to load reader manifest.";
          setError(msg);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  const hasPresenter = !!manifest?.presenter;

  // Poll the composited-MP4 export status (lip-sync presenters only).
  // Re-arms whenever the status returns to "running" (e.g. after Export).
  useEffect(() => {
    if (!id || !hasPresenter) return;
    if (exportStatus === "done" || exportStatus === "failed") return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = () => {
      getMp4ExportStatus(id)
        .then((state) => {
          if (cancelled) return;
          setExportStatus(state.export_status);
          setExportError(state.export_error);
          if (state.export_status === "running") {
            timer = setTimeout(poll, 3000);
          }
        })
        .catch(() => undefined);
    };
    poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id, hasPresenter, exportStatus]);

  const handleExport = useCallback(async () => {
    if (!id) return;
    setExportError(null);
    setExportStatus("running");
    try {
      const state = await requestMp4Export(id);
      setExportStatus(state.export_status ?? "running");
    } catch {
      setExportStatus("failed");
      setExportError("Could not start the MP4 export.");
    }
  }, [id]);

  const flatWords = useMemo(() => {
    if (!manifest) return [];
    const all: FlatWord[] = [];
    for (const chunk of manifest.chunks) {
      const page = chunk.pages[0] ?? 0;
      for (const w of chunk.words) {
        all.push({ page, ...w });
      }
    }
    return all;
  }, [manifest]);

  const pages = useMemo(() => {
    if (!manifest) return [];
    const grouped = new Map<number, ReaderChunk[]>();
    for (const chunk of manifest.chunks) {
      const page = chunk.pages[0] ?? 0;
      const current = grouped.get(page) || [];
      current.push(chunk);
      grouped.set(page, current);
    }
    return Array.from(grouped.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([page, chunks]) => ({ page, chunks }));
  }, [manifest]);

  const activePage = useMemo(() => {
    const wordPage = activeIdx >= 0 ? flatWords[activeIdx]?.page ?? 0 : 0;
    if (wordPage > 0) return wordPage;
    return pages[0]?.page ?? 0;
  }, [activeIdx, flatWords, pages]);

  const activePageImage = useMemo(() => {
    if (!id || !manifest?.pages || activePage <= 0) return null;
    const filename = manifest.pages.files[String(activePage)];
    if (!filename) return null;
    return {
      page: activePage,
      url: getReaderPageUrl(id, filename),
    };
  }, [activePage, id, manifest]);

  const handleTimeUpdate = useCallback(() => {
    const el = mediaRef.current;
    if (!el) return;
    const t = el.currentTime;
    setCurrentTime(t);
    const idx = findActiveWordIndex(flatWords, t);
    setActiveIdx((prev) => (prev === idx ? prev : idx));
  }, [flatWords]);

  useEffect(() => {
    if (!autoScroll || activeIdx < 0) return;
    const container = containerRef.current;
    const scroller = scrollerRef.current;
    if (!container || !scroller) return;
    const node = container.querySelector<HTMLElement>(`[data-w="${activeIdx}"]`);
    if (!node) return;

    const scrollerRect = scroller.getBoundingClientRect();
    const nodeRect = node.getBoundingClientRect();
    const relativeY = nodeRect.top - scrollerRect.top;
    const scrollerH = scroller.clientHeight;
    // Comfort band: 25%–65% of viewport. Only scroll when the active word
    // leaves the band, then reposition it near the top of the band so there's
    // a stretch of comfortable reading before the next jump.
    const bandTop = scrollerH * 0.25;
    const bandBottom = scrollerH * 0.65;
    if (relativeY >= bandTop && relativeY + nodeRect.height <= bandBottom) {
      return;
    }
    const desiredRelativeY = scrollerH * 0.3;
    const delta = relativeY - desiredRelativeY;
    const maxScroll = scroller.scrollHeight - scroller.clientHeight;
    const nextTarget = Math.max(
      0,
      Math.min(maxScroll, scroller.scrollTop + delta),
    );
    scrollTargetRef.current = nextTarget;

    if (rafRef.current != null) return;
    const step = () => {
      const s = scrollerRef.current;
      const tgt = scrollTargetRef.current;
      if (!s || tgt == null) {
        rafRef.current = null;
        return;
      }
      const current = s.scrollTop;
      const diff = tgt - current;
      if (Math.abs(diff) < 0.5) {
        s.scrollTop = tgt;
        scrollTargetRef.current = null;
        rafRef.current = null;
        return;
      }
      s.scrollTop = current + diff * 0.12;
      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
  }, [activeIdx, autoScroll]);

  useEffect(() => {
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const cancelAutoScroll = useCallback(() => {
    setAutoScroll(false);
    scrollTargetRef.current = null;
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  const revealControls = useCallback(() => {
    setControlsVisible(true);
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    if (!hasStartedPlayingRef.current) {
      hideTimerRef.current = null;
      return;
    }
    hideTimerRef.current = setTimeout(() => {
      setControlsVisible(false);
      hideTimerRef.current = null;
    }, 2500);
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (e.clientY > window.innerHeight - 160) {
        revealControls();
      }
    };
    window.addEventListener("mousemove", onMove);
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, [revealControls]);

  useEffect(() => {
    if (!hasStartedPlaying) return;
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => {
      setControlsVisible(false);
      hideTimerRef.current = null;
    }, 2500);
    return () => {
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
    };
  }, [hasStartedPlaying]);

  const seekToWord = useCallback(
    (idx: number) => {
      const el = mediaRef.current;
      const target = flatWords[idx];
      if (!el || !target) return;
      el.currentTime = Math.max(0, target.start - 0.02);
      setCurrentTime(el.currentTime);
      if (el.paused) {
        el.play().catch(() => undefined);
      }
    },
    [flatWords],
  );

  const togglePlay = useCallback(() => {
    const el = mediaRef.current;
    if (!el) return;
    if (el.paused) {
      el.play().catch(() => undefined);
    } else {
      el.pause();
    }
  }, []);

  const handleRateChange = useCallback((next: number) => {
    setRate(next);
    if (mediaRef.current) mediaRef.current.playbackRate = next;
  }, []);

  const handleScrub = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const el = mediaRef.current;
    if (!el) return;
    const nextTime = Number(e.target.value);
    el.currentTime = nextTime;
    setCurrentTime(nextTime);
  }, []);

  // -- PiP drag & edge-resize ------------------------------------------------
  const onPipPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const el = e.currentTarget;
      const zone = pipZoneAt(el, e.clientX, e.clientY);
      if (zone === "drag") {
        pipGestureRef.current = {
          type: "drag",
          dx: e.clientX - pipPos.x,
          dy: e.clientY - pipPos.y,
        };
        setPipCursor("grabbing");
      } else {
        const r = el.getBoundingClientRect();
        pipGestureRef.current = {
          type: "resize",
          mode: zone,
          startW: r.width,
          startX: e.clientX,
          startY: e.clientY,
          aspect: r.height > 0 ? r.width / r.height : 16 / 9,
        };
      }
      el.setPointerCapture(e.pointerId);
    },
    [pipPos],
  );

  const onPipPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const el = e.currentTarget;
      const g = pipGestureRef.current;
      if (!g) {
        // Idle hover: reflect the resize/drag affordance in the cursor.
        setPipCursor(ZONE_CURSOR[pipZoneAt(el, e.clientX, e.clientY)]);
        return;
      }
      if (g.type === "drag") {
        const maxX = Math.max(0, window.innerWidth - el.offsetWidth);
        const maxY = Math.max(0, window.innerHeight - el.offsetHeight);
        setPipPos({
          x: Math.min(Math.max(0, e.clientX - g.dx), maxX),
          y: Math.min(Math.max(0, e.clientY - g.dy), maxY),
        });
      } else {
        // Width is the only free dimension — height tracks the video aspect.
        const delta =
          g.mode === "s"
            ? (e.clientY - g.startY) * g.aspect
            : e.clientX - g.startX;
        const maxFit = window.innerWidth - pipPos.x;
        const next = Math.min(
          Math.max(PIP_MIN_W, g.startW + delta),
          Math.min(PIP_MAX_W, maxFit),
        );
        setPipWidth(next);
      }
    },
    [pipPos],
  );

  const onPipPointerUp = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    pipGestureRef.current = null;
    setPipCursor(ZONE_CURSOR[pipZoneAt(e.currentTarget, e.clientX, e.clientY)]);
  }, []);

  const colors = THEMES[theme];
  const rootStyle = {
    "--reader-bg": colors.bg,
    "--reader-fg": colors.fg,
    "--reader-surface": colors.surface,
    "--reader-border": colors.border,
    "--reader-muted": colors.muted,
    "--reader-highlight-bg": colors.highlightBg,
    "--reader-highlight-fg": colors.highlightFg,
    "--reader-hover": colors.hover,
  } as CSSProperties;

  const duration = manifest?.duration ?? 0;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        Loading reader...
      </div>
    );
  }

  if (error || !manifest) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-center px-4">
        <p className="text-red-600 max-w-md">{error || "Reader unavailable."}</p>
        <Link
          to={id ? `/jobs/${id}` : "/"}
          className="text-sm text-blue-600 hover:underline"
        >
          Back to job
        </Link>
      </div>
    );
  }

  let wordCounter = 0;

  const mediaHandlers = {
    onTimeUpdate: handleTimeUpdate,
    onPlay: () => {
      setPlaying(true);
      if (!hasStartedPlayingRef.current) {
        hasStartedPlayingRef.current = true;
        setHasStartedPlaying(true);
      }
    },
    onPause: () => setPlaying(false),
  };

  return (
    <div
      style={rootStyle}
      className="fixed inset-0 flex flex-col bg-[var(--reader-bg)] text-[var(--reader-fg)]"
    >
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--reader-border)] bg-[var(--reader-surface)]">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to={id ? `/jobs/${id}` : "/"}
            className="text-[var(--reader-muted)] hover:text-[var(--reader-fg)] text-sm shrink-0"
          >
            ← Back
          </Link>
          <h1 className="text-base sm:text-lg font-semibold truncate">
            {manifest.title}
          </h1>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-3">
          <button
            type="button"
            onClick={() => setTheme((t) => (t === "night" ? "pdf" : "night"))}
            className="text-xs rounded-md border border-[var(--reader-border)] px-2.5 py-1 hover:bg-[var(--reader-hover)] transition"
            aria-label="Toggle theme"
          >
            {theme === "night" ? "☾ Night" : "☀ PDF"}
          </button>
          {hasPresenter && !pipVisible && (
            <button
              type="button"
              onClick={() => setPipVisible(true)}
              className="text-xs rounded-md border border-[var(--reader-border)] px-2.5 py-1 hover:bg-[var(--reader-hover)] transition"
            >
              Show presenter
            </button>
          )}
          {id && hasPresenter && (
            <>
              {exportStatus === "done" ? (
                <a
                  href={getMp4ExportDownloadUrl(id)}
                  className="text-xs rounded-md border border-[var(--reader-border)] px-2.5 py-1 hover:bg-[var(--reader-hover)] transition"
                >
                  ↓ Composited MP4
                </a>
              ) : exportStatus === "running" ? (
                <span className="text-xs text-[var(--reader-muted)] px-1">
                  Baking MP4…
                </span>
              ) : (
                <button
                  type="button"
                  onClick={handleExport}
                  title={
                    exportStatus === "failed"
                      ? exportError || "The MP4 export failed — click to retry."
                      : undefined
                  }
                  className="text-xs rounded-md border border-[var(--reader-border)] px-2.5 py-1 hover:bg-[var(--reader-hover)] transition"
                >
                  {exportStatus === "failed"
                    ? "Retry MP4 export"
                    : "Export composited MP4"}
                </button>
              )}
            </>
          )}
          {id && !hasPresenter && (
            <a
              href={getDownloadUrl(id)}
              className="text-sm text-blue-500 hover:underline"
            >
              Download Output
            </a>
          )}
        </div>
      </header>

      <main
        ref={scrollerRef}
        className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 pb-24"
      >
        <div
          className={
            "max-w-6xl mx-auto " +
            (activePageImage ? "lg:grid lg:grid-cols-[22rem_minmax(0,1fr)] lg:gap-8" : "")
          }
        >
          {activePageImage && (
            <aside className="hidden lg:block">
              <div className="sticky top-6 rounded-3xl bg-[var(--reader-surface)] border border-[var(--reader-border)] shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--reader-border)] text-xs uppercase tracking-[0.2em] text-[var(--reader-muted)]">
                  <span>Page {activePageImage.page}</span>
                  <button
                    type="button"
                    onClick={() => setInvertPages((v) => !v)}
                    className="normal-case tracking-normal rounded border border-[var(--reader-border)] px-1.5 py-0.5 hover:bg-[var(--reader-hover)] transition"
                  >
                    {invertPages ? "Original" : "Invert"}
                  </button>
                </div>
                <img
                  src={activePageImage.url}
                  alt={`Page ${activePageImage.page}`}
                  className="w-full h-auto block"
                  style={
                    invertPages
                      ? { filter: "invert(1) hue-rotate(180deg)" }
                      : undefined
                  }
                />
              </div>
            </aside>
          )}

          <article
            ref={containerRef}
            className={
              "leading-relaxed text-lg sm:text-xl font-serif " +
              (activePageImage ? "min-w-0" : "max-w-2xl mx-auto")
            }
            onWheel={cancelAutoScroll}
            onTouchMove={cancelAutoScroll}
          >
            {pages.map(({ page, chunks }) => (
              <section key={page} className="mb-10">
                {page > 0 && (
                  <div className="text-xs uppercase tracking-wider text-[var(--reader-muted)] mb-3">
                    Page {page}
                  </div>
                )}
                {chunks.map((chunk) => (
                  <p key={chunk.chunk_num} className="mb-5">
                    {chunk.words.length === 0 ? (
                      <span>{chunk.text}</span>
                    ) : (
                      chunk.words.map((w) => {
                        const idx = wordCounter++;
                        const isActive = idx === activeIdx;
                        return (
                          <span
                            key={idx}
                            data-w={idx}
                            onClick={() => seekToWord(idx)}
                            className={
                              "cursor-pointer transition-colors rounded px-0.5 " +
                              (isActive
                                ? "bg-[var(--reader-highlight-bg)] text-[var(--reader-highlight-fg)]"
                                : "hover:bg-[var(--reader-hover)]")
                            }
                          >
                            {w.word}{" "}
                          </span>
                        );
                      })
                    )}
                  </p>
                ))}
              </section>
            ))}
          </article>
        </div>
      </main>

      {hasPresenter ? (
        <div
          // Picture-in-picture presenter. Kept mounted at all times — it is the
          // playback clock. Drag from anywhere on the video; resize by dragging
          // the right / bottom edges or the bottom-right corner.
          onPointerDown={onPipPointerDown}
          onPointerMove={onPipPointerMove}
          onPointerUp={onPipPointerUp}
          style={{
            left: pipPos.x,
            top: pipPos.y,
            width: pipWidth,
            cursor: pipCursor,
            display: pipVisible ? "block" : "none",
          }}
          className="group fixed z-30 rounded-xl overflow-hidden border border-[var(--reader-border)] shadow-2xl bg-black select-none touch-none"
        >
          <button
            type="button"
            // stopPropagation keeps the container's drag handler from
            // pointer-capturing this click.
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => setPipVisible(false)}
            aria-label="Hide presenter"
            className="absolute top-1.5 right-1.5 z-10 grid h-6 w-6 place-items-center rounded-full bg-black/60 text-white text-xs leading-none opacity-0 transition hover:bg-black/80 group-hover:opacity-100 pointer-events-auto"
          >
            ✕
          </button>
          <video
            ref={(el) => {
              mediaRef.current = el;
            }}
            src={id ? getReaderPresenterUrl(id) : undefined}
            playsInline
            preload="auto"
            className="w-full block bg-black pointer-events-none"
            {...mediaHandlers}
          />
        </div>
      ) : (
        <audio
          ref={(el) => {
            mediaRef.current = el;
          }}
          src={id ? getReaderAudioUrl(id) : undefined}
          preload="auto"
          {...mediaHandlers}
        />
      )}

      <div
        className="absolute bottom-0 inset-x-0 z-20"
        onMouseEnter={revealControls}
        onMouseMove={revealControls}
      >
        <footer
          className={
            "bg-[var(--reader-surface)] border-t border-[var(--reader-border)] shadow-[0_-8px_24px_-12px_rgba(0,0,0,0.35)] transform transition-all duration-300 ease-out " +
            (controlsVisible
              ? "translate-y-0 opacity-100"
              : "translate-y-full opacity-0 pointer-events-none")
          }
        >
          <div className="max-w-4xl mx-auto px-4 py-3 flex flex-col gap-2">
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  setAutoScroll(true);
                  togglePlay();
                }}
                className="w-12 h-12 rounded-full bg-[var(--reader-fg)] text-[var(--reader-bg)] flex items-center justify-center shadow-md hover:shadow-lg hover:scale-105 active:scale-95 transition-[transform,box-shadow] duration-150 shrink-0"
                aria-label={playing ? "Pause" : "Play"}
              >
                {playing ? (
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <rect x="6" y="5" width="4" height="14" rx="1" />
                    <rect x="14" y="5" width="4" height="14" rx="1" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 ml-0.5" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M8 5.14v13.72c0 .79.87 1.26 1.54.83l10.8-6.86a.98.98 0 0 0 0-1.66L9.54 4.31A.98.98 0 0 0 8 5.14z" />
                  </svg>
                )}
              </button>
              <span className="text-xs text-[var(--reader-muted)] tabular-nums w-10 text-right">
                {fmtTime(currentTime)}
              </span>
              <input
                type="range"
                min={0}
                max={duration || 0}
                step={0.1}
                value={currentTime}
                onChange={handleScrub}
                className="flex-1 accent-[var(--reader-highlight-bg)]"
              />
              <span className="text-xs text-[var(--reader-muted)] tabular-nums w-10">
                {fmtTime(duration)}
              </span>
              <select
                value={rate}
                onChange={(e) => handleRateChange(Number(e.target.value))}
                className="text-xs border border-[var(--reader-border)] rounded px-1 py-0.5 bg-[var(--reader-bg)] text-[var(--reader-fg)] shrink-0"
                aria-label="Playback speed"
              >
                {PLAYBACK_RATES.map((nextRate) => (
                  <option key={nextRate} value={nextRate}>
                    {nextRate}×
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 text-xs text-[var(--reader-muted)] sm:self-end">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
              />
              Auto-scroll to current word
            </label>
          </div>
        </footer>
      </div>
    </div>
  );
}
