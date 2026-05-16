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
import { getDownloadUrl } from "../api/jobs";
import { ReaderChunk, ReaderManifest } from "../types";

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
const PIP_SIZES = [200, 280, 380];
const THEME_KEY = "reader-theme";
const PIP_POS_KEY = "reader-pip-pos";
const PIP_SIZE_KEY = "reader-pip-size";

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
  const [pipVisible, setPipVisible] = useState(true);
  const [pipSizeIdx, setPipSizeIdx] = useState<number>(() => {
    const stored = Number(localStorage.getItem(PIP_SIZE_KEY));
    return Number.isInteger(stored) && stored >= 0 && stored < PIP_SIZES.length
      ? stored
      : 1;
  });
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
  const dragRef = useRef<{ dx: number; dy: number } | null>(null);

  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(PIP_SIZE_KEY, String(pipSizeIdx));
  }, [pipSizeIdx]);

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

  // -- PiP drag --------------------------------------------------------------
  const onPipPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      dragRef.current = {
        dx: e.clientX - pipPos.x,
        dy: e.clientY - pipPos.y,
      };
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    },
    [pipPos],
  );

  const onPipPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (!drag) return;
      const width = PIP_SIZES[pipSizeIdx];
      const maxX = Math.max(0, window.innerWidth - width);
      const maxY = Math.max(0, window.innerHeight - 80);
      setPipPos({
        x: Math.min(Math.max(0, e.clientX - drag.dx), maxX),
        y: Math.min(Math.max(0, e.clientY - drag.dy), maxY),
      });
    },
    [pipSizeIdx],
  );

  const onPipPointerUp = useCallback(() => {
    dragRef.current = null;
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
          // playback clock — and merely collapsed via `display:none` when hidden.
          style={{
            left: pipPos.x,
            top: pipPos.y,
            width: PIP_SIZES[pipSizeIdx],
            display: pipVisible ? "block" : "none",
          }}
          className="fixed z-30 rounded-xl overflow-hidden border border-[var(--reader-border)] shadow-2xl bg-black"
        >
          <div
            onPointerDown={onPipPointerDown}
            onPointerMove={onPipPointerMove}
            onPointerUp={onPipPointerUp}
            className="flex items-center justify-between px-2 py-1 bg-[var(--reader-surface)] cursor-move select-none touch-none"
          >
            <span className="text-[10px] uppercase tracking-wider text-[var(--reader-muted)]">
              Presenter
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() =>
                  setPipSizeIdx((i) => (i + 1) % PIP_SIZES.length)
                }
                className="text-[10px] rounded px-1 text-[var(--reader-muted)] hover:bg-[var(--reader-hover)]"
                aria-label="Resize presenter"
              >
                ⤢
              </button>
              <button
                type="button"
                onClick={() => setPipVisible(false)}
                className="text-[10px] rounded px-1 text-[var(--reader-muted)] hover:bg-[var(--reader-hover)]"
                aria-label="Hide presenter"
              >
                ✕
              </button>
            </div>
          </div>
          <video
            ref={(el) => {
              mediaRef.current = el;
            }}
            src={id ? getReaderPresenterUrl(id) : undefined}
            playsInline
            preload="auto"
            className="w-full block bg-black"
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
