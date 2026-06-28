import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import { lipsyncPresetVideoUrl } from "../api/lipsyncPresets";
import { getUploadPreviewUrl } from "../api/uploads";
import type { LipsyncConfig, UploadedFile } from "../types";

interface Props {
  uploadedFile?: UploadedFile | null;
  config: LipsyncConfig;
}

type ThemeName = "night" | "pdf";

interface ThemeColors {
  bg: string;
  fg: string;
  surface: string;
  border: string;
  muted: string;
  accent: string;
}

// Mirrors the Reader page palette so the preview matches "open in reader".
const THEMES: Record<ThemeName, ThemeColors> = {
  night: {
    bg: "#0b0b0c",
    fg: "#e8e8ea",
    surface: "#18181b",
    border: "#2e2e33",
    muted: "#9a9aa2",
    accent: "#facc15",
  },
  pdf: {
    bg: "#f7f1e3",
    fg: "#1f2937",
    surface: "#fffaf0",
    border: "#e8dcc2",
    muted: "#8d7751",
    accent: "#fcd34d",
  },
};

// `face_position` only seeds which corner the presenter starts in; the reader
// lets the viewer drag it anywhere, so this preview does too.
const PIP_CORNER: Record<string, { v: "top" | "bottom"; h: "left" | "right" }> = {
  "top-left": { v: "top", h: "left" },
  "top-right": { v: "top", h: "right" },
  "bottom-left": { v: "bottom", h: "left" },
  "bottom-right": { v: "bottom", h: "right" },
  left: { v: "bottom", h: "left" },
  right: { v: "bottom", h: "right" },
  center: { v: "top", h: "right" },
};

const PIP_MARGIN = 12;
const THEME_KEY = "reader-theme";

function isTextDocument(file: UploadedFile | null | undefined): boolean {
  if (!file) return false;
  return (
    file.content_type.startsWith("text/") ||
    file.original_name.toLowerCase().endsWith(".txt")
  );
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function loadTheme(): ThemeName {
  return localStorage.getItem(THEME_KEY) === "pdf" ? "pdf" : "night";
}

export default function LipsyncPreviewFrame({ uploadedFile, config }: Props) {
  const frameRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ dx: number; dy: number } | null>(null);
  const [frameSize, setFrameSize] = useState({ w: 0, h: 0 });
  const [documentText, setDocumentText] = useState<string | null>(null);
  const [theme, setTheme] = useState<ThemeName>(loadTheme);
  const [dragging, setDragging] = useState(false);
  // `null` means "follow the seeded corner"; a point means the user dragged it.
  const [pipPos, setPipPos] = useState<{ x: number; y: number } | null>(null);

  const canPreview =
    !!uploadedFile && (!!config.preset_id || !!config.ref_video_file_id);
  const documentUrl = uploadedFile ? getUploadPreviewUrl(uploadedFile.id) : null;
  const videoUrl = config.preset_id
    ? lipsyncPresetVideoUrl(config.preset_id)
    : config.ref_video_file_id
    ? getUploadPreviewUrl(config.ref_video_file_id)
    : null;
  const isText = isTextDocument(uploadedFile);
  const colors = THEMES[theme];

  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (rect) setFrameSize({ w: rect.width, h: rect.height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Re-seed the presenter to the configured corner when that setting changes.
  useEffect(() => {
    setPipPos(null);
  }, [config.face_position]);

  useEffect(() => {
    if (!uploadedFile || !documentUrl || !isTextDocument(uploadedFile)) {
      setDocumentText(null);
      return;
    }
    let cancelled = false;
    fetch(documentUrl)
      .then((resp) => (resp.ok ? resp.text() : ""))
      .then((text) => {
        if (!cancelled) setDocumentText(text.trim() || "Preview text");
      })
      .catch(() => {
        if (!cancelled) setDocumentText("Preview text");
      });
    return () => {
      cancelled = true;
    };
  }, [documentUrl, uploadedFile]);

  const corner = PIP_CORNER[config.face_position] ?? PIP_CORNER["bottom-right"];

  // Presenter box: width from `face_scale`, height locked to a 16:9 video.
  const pip = useMemo(() => {
    const { w: fw, h: fh } = frameSize;
    const width = Math.max(72, fw * clamp(config.face_scale, 0.1, 0.6));
    const height = (width * 9) / 16;
    const maxX = Math.max(0, fw - width);
    const maxY = Math.max(0, fh - height);
    let x: number;
    let y: number;
    if (pipPos) {
      x = pipPos.x;
      y = pipPos.y;
    } else {
      x = corner.h === "left" ? PIP_MARGIN : fw - width - PIP_MARGIN;
      y = corner.v === "top" ? PIP_MARGIN : fh - height - PIP_MARGIN;
    }
    return {
      width,
      height,
      x: clamp(x, 0, maxX),
      y: clamp(y, 0, maxY),
      maxX,
      maxY,
    };
  }, [frameSize, config.face_scale, corner, pipPos]);

  const onPipPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    const frame = frameRef.current?.getBoundingClientRect();
    if (!frame) return;
    dragRef.current = {
      dx: e.clientX - frame.left - pip.x,
      dy: e.clientY - frame.top - pip.y,
    };
    setDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPipPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const grab = dragRef.current;
    const frame = frameRef.current?.getBoundingClientRect();
    if (!grab || !frame) return;
    setPipPos({
      x: clamp(e.clientX - frame.left - grab.dx, 0, pip.maxX),
      y: clamp(e.clientY - frame.top - grab.dy, 0, pip.maxY),
    });
  };

  const onPipPointerUp = () => {
    dragRef.current = null;
    setDragging(false);
  };

  const renderDocument = () => {
    if (!uploadedFile || !documentUrl) return null;
    if (isText) {
      return (
        <div
          className="h-full overflow-y-auto px-6 py-5 font-serif text-[13px] leading-7 whitespace-pre-wrap break-words"
          style={{ color: colors.fg }}
        >
          {documentText ?? "Loading preview…"}
        </div>
      );
    }
    // Non-text docs (PDF/EPUB) render their own preview; strip the native PDF
    // chrome so it reads as a reading surface rather than a viewer.
    return (
      <object
        data={`${documentUrl}#toolbar=0&navpanes=0&view=FitH`}
        type={uploadedFile.content_type}
        className="h-full w-full"
      >
        <div
          className="flex h-full items-center justify-center px-4 text-center text-xs"
          style={{ color: colors.muted }}
        >
          {uploadedFile.original_name}
        </div>
      </object>
    );
  };

  const rootStyle: CSSProperties = { backgroundColor: colors.bg, color: colors.fg };

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Reader Preview</h3>
          <p className="text-xs text-gray-500">
            How this job looks under “Open in reader” — drag the presenter to
            reposition it.
          </p>
        </div>
      </div>

      {canPreview && videoUrl ? (
        <div
          className="overflow-hidden rounded-xl border shadow-sm"
          style={{ borderColor: colors.border }}
        >
          {/* Reader header */}
          <div
            className="flex items-center justify-between gap-3 border-b px-4 py-2.5"
            style={{ backgroundColor: colors.surface, borderColor: colors.border }}
          >
            <span className="min-w-0 truncate text-xs font-semibold">
              {uploadedFile?.original_name ?? "Document"}
            </span>
            <button
              type="button"
              onClick={() => setTheme((t) => (t === "night" ? "pdf" : "night"))}
              className="shrink-0 rounded-md border px-2.5 py-1 text-xs font-medium transition"
              style={{ borderColor: colors.border, color: colors.fg }}
            >
              {theme === "night" ? "☾ Night" : "☀ Reader"}
            </button>
          </div>

          {/* Reading surface with the floating presenter */}
          <div
            ref={frameRef}
            className="relative h-[360px] overflow-hidden"
            style={rootStyle}
          >
            {renderDocument()}
            <div
              onPointerDown={onPipPointerDown}
              onPointerMove={onPipPointerMove}
              onPointerUp={onPipPointerUp}
              className="absolute touch-none select-none overflow-hidden rounded-lg border border-black/40 bg-black shadow-2xl"
              style={{
                left: pip.x,
                top: pip.y,
                width: pip.width,
                height: pip.height,
                cursor: dragging ? "grabbing" : "grab",
              }}
            >
              <video
                src={videoUrl}
                muted
                playsInline
                preload="metadata"
                className="pointer-events-none h-full w-full object-cover"
                onLoadedMetadata={(e) => {
                  e.currentTarget.currentTime = Math.min(
                    1,
                    e.currentTarget.duration || 1,
                  );
                }}
              />
            </div>
          </div>

          {/* Reader control bar (decorative) */}
          <div
            className="flex items-center gap-3 border-t px-4 py-2.5"
            style={{ backgroundColor: colors.surface, borderColor: colors.border }}
          >
            <span
              className="grid h-7 w-7 shrink-0 place-items-center rounded-full"
              style={{ backgroundColor: colors.fg, color: colors.bg }}
            >
              <svg className="ml-0.5 h-3 w-3" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <path d="M8 5.14v13.72c0 .79.87 1.26 1.54.83l10.8-6.86a.98.98 0 0 0 0-1.66L9.54 4.31A.98.98 0 0 0 8 5.14z" />
              </svg>
            </span>
            <span className="text-[10px] tabular-nums" style={{ color: colors.muted }}>
              0:00
            </span>
            <div
              className="h-1 flex-1 rounded-full"
              style={{ backgroundColor: colors.border }}
            >
              <div
                className="h-1 w-1/4 rounded-full"
                style={{ backgroundColor: colors.accent }}
              />
            </div>
            <span className="text-[10px] tabular-nums" style={{ color: colors.muted }}>
              1×
            </span>
          </div>
        </div>
      ) : (
        <div className="flex h-[360px] items-center justify-center rounded-xl border border-dashed border-gray-300 bg-gray-50 text-xs text-gray-500">
          Upload a document and reference video to preview the reader.
        </div>
      )}

      <p className="mt-2 text-xs text-gray-500">
        Theme and presenter placement stay adjustable in the reader — this is
        just a starting point seeded from the settings above.
      </p>
    </div>
  );
}
