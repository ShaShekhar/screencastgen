import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getReaderAudioUrl,
  getReaderManifest,
  getReaderPageUrl,
} from "../api/reader";
import { getDownloadUrl } from "../api/jobs";
import { ReaderChunk, ReaderManifest } from "../types";

interface FlatWord {
  word: string;
  start: number;
  end: number;
  page: number;
}

const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 1.75, 2];

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

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

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
              ? "This job does not have a browser reader available. Re-run the highlight pipeline to generate one."
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
    const el = audioRef.current;
    if (!el) return;
    const t = el.currentTime;
    setCurrentTime(t);
    const idx = findActiveWordIndex(flatWords, t);
    setActiveIdx((prev) => (prev === idx ? prev : idx));
  }, [flatWords]);

  useEffect(() => {
    if (!autoScroll || activeIdx < 0 || !containerRef.current) return;
    const node = containerRef.current.querySelector<HTMLElement>(
      `[data-w="${activeIdx}"]`,
    );
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activeIdx, autoScroll]);

  const seekToWord = useCallback(
    (idx: number) => {
      const el = audioRef.current;
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
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) {
      el.play().catch(() => undefined);
    } else {
      el.pause();
    }
  }, []);

  const handleRateChange = useCallback((next: number) => {
    setRate(next);
    if (audioRef.current) audioRef.current.playbackRate = next;
  }, []);

  const handleScrub = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const el = audioRef.current;
    if (!el) return;
    const nextTime = Number(e.target.value);
    el.currentTime = nextTime;
    setCurrentTime(nextTime);
  }, []);

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

  return (
    <div className="fixed inset-0 bg-[#f7f1e3] text-gray-900 flex flex-col">
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white/85 backdrop-blur">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to={id ? `/jobs/${id}` : "/"}
            className="text-gray-500 hover:text-gray-900 text-sm shrink-0"
          >
            ← Back
          </Link>
          <h1 className="text-base sm:text-lg font-semibold truncate">
            {manifest.title}
          </h1>
        </div>
        {id && (
          <a
            href={getDownloadUrl(id)}
            className="text-sm text-blue-600 hover:underline shrink-0 ml-3"
          >
            Download Output
          </a>
        )}
      </header>

      <main className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 pb-40">
        <div
          className={
            "max-w-6xl mx-auto " +
            (activePageImage ? "lg:grid lg:grid-cols-[22rem_minmax(0,1fr)] lg:gap-8" : "")
          }
        >
          {activePageImage && (
            <aside className="hidden lg:block">
              <div className="sticky top-6 rounded-3xl bg-[#fffaf0] border border-[#e8dcc2] shadow-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-[#eadfca] text-xs uppercase tracking-[0.2em] text-[#8d7751]">
                  Page {activePageImage.page}
                </div>
                <img
                  src={activePageImage.url}
                  alt={`Page ${activePageImage.page}`}
                  className="w-full h-auto block"
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
            onWheel={() => setAutoScroll(false)}
            onTouchMove={() => setAutoScroll(false)}
          >
            {pages.map(({ page, chunks }) => (
              <section key={page} className="mb-10">
                {page > 0 && (
                  <div className="text-xs uppercase tracking-wider text-gray-400 mb-3">
                    Page {page}
                  </div>
                )}
                {chunks.map((chunk) => (
                  <p key={chunk.chunk_num} className="mb-5">
                    {chunk.words.length === 0 ? (
                      <span className="text-gray-700">{chunk.text}</span>
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
                                ? "bg-amber-300 text-gray-900"
                                : "hover:bg-amber-100")
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

      <footer className="absolute bottom-0 inset-x-0 bg-white border-t border-gray-200 shadow-lg">
        <audio
          ref={audioRef}
          src={id ? getReaderAudioUrl(id) : undefined}
          onTimeUpdate={handleTimeUpdate}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          preload="auto"
        />
        <div className="max-w-4xl mx-auto px-4 py-3 flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setAutoScroll(true);
                togglePlay();
              }}
              className="w-10 h-10 rounded-full bg-gray-900 text-white flex items-center justify-center hover:bg-gray-700 transition shrink-0"
              aria-label={playing ? "Pause" : "Play"}
            >
              {playing ? "❚❚" : "▶"}
            </button>
            <span className="text-xs text-gray-500 tabular-nums w-10 text-right">
              {fmtTime(currentTime)}
            </span>
            <input
              type="range"
              min={0}
              max={duration || 0}
              step={0.1}
              value={currentTime}
              onChange={handleScrub}
              className="flex-1 accent-gray-900"
            />
            <span className="text-xs text-gray-500 tabular-nums w-10">
              {fmtTime(duration)}
            </span>
            <select
              value={rate}
              onChange={(e) => handleRateChange(Number(e.target.value))}
              className="text-xs border border-gray-300 rounded px-1 py-0.5 bg-white shrink-0"
              aria-label="Playback speed"
            >
              {PLAYBACK_RATES.map((nextRate) => (
                <option key={nextRate} value={nextRate}>
                  {nextRate}×
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-500 sm:self-end">
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
  );
}
