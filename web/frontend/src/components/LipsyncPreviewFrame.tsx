import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { getUploadPreviewUrl } from "../api/uploads";
import type { LipsyncConfig, UploadedFile } from "../types";

interface Props {
  uploadedFile?: UploadedFile | null;
  config: LipsyncConfig;
}

type ThemeName = "night" | "pdf";

const THEMES: Record<ThemeName, { bg: string; fg: string }> = {
  night: { bg: "#0b0b0c", fg: "#e8e8ea" },
  pdf: { bg: "#f7f1e3", fg: "#1f2937" },
};

// The reader viewer floats the presenter as a movable picture-in-picture.
// `face_position` only seeds which corner it starts in; split/center layouts
// from the old baked-MP4 composite collapse to a sensible corner here.
const PIP_CORNER: Record<string, { v: "top" | "bottom"; h: "left" | "right" }> = {
  "top-left": { v: "top", h: "left" },
  "top-right": { v: "top", h: "right" },
  "bottom-left": { v: "bottom", h: "left" },
  "bottom-right": { v: "bottom", h: "right" },
  left: { v: "bottom", h: "left" },
  right: { v: "bottom", h: "right" },
  center: { v: "top", h: "right" },
};

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

export default function LipsyncPreviewFrame({ uploadedFile, config }: Props) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [frameDisplayWidth, setFrameDisplayWidth] = useState(0);
  const [documentText, setDocumentText] = useState<string | null>(null);
  const [theme, setTheme] = useState<ThemeName>("night");

  const canPreview = !!uploadedFile && !!config.ref_video_file_id;
  const documentUrl = uploadedFile ? getUploadPreviewUrl(uploadedFile.id) : null;
  const videoUrl = config.ref_video_file_id
    ? getUploadPreviewUrl(config.ref_video_file_id)
    : null;
  const isText = isTextDocument(uploadedFile);

  useEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      setFrameDisplayWidth(entries[0]?.contentRect.width ?? 0);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!uploadedFile || !documentUrl || !isTextDocument(uploadedFile)) {
      setDocumentText(null);
      return;
    }
    let cancelled = false;
    fetch(documentUrl)
      .then((resp) => (resp.ok ? resp.text() : ""))
      .then((text) => {
        if (!cancelled) setDocumentText(text.trim() || "Preview frame");
      })
      .catch(() => {
        if (!cancelled) setDocumentText("Preview frame");
      });
    return () => {
      cancelled = true;
    };
  }, [documentUrl, uploadedFile]);

  const previewFontSize = Math.max(
    10,
    config.font_size * (frameDisplayWidth ? frameDisplayWidth / config.width : 0.5),
  );

  const corner = PIP_CORNER[config.face_position] ?? PIP_CORNER["bottom-right"];
  const pipStyle = useMemo<CSSProperties>(() => {
    const widthPct = clamp(config.face_scale, 0.1, 0.6) * 100;
    const style: CSSProperties = { width: `${widthPct}%` };
    style[corner.v] = "4%";
    style[corner.h] = "4%";
    return style;
  }, [config.face_scale, corner]);

  const colors = THEMES[theme];

  const renderDocument = () => {
    if (!uploadedFile || !documentUrl) return null;
    if (isText) {
      return (
        <div
          className="h-full overflow-hidden whitespace-pre-wrap break-words p-4 leading-relaxed"
          style={{ fontSize: previewFontSize, color: colors.fg }}
        >
          {documentText ?? "Loading preview..."}
        </div>
      );
    }
    return (
      <object
        data={documentUrl}
        type={uploadedFile.content_type}
        className="h-full w-full bg-white"
      >
        <div className="flex h-full items-center justify-center px-4 text-center text-xs text-gray-300">
          {uploadedFile.original_name}
        </div>
      </object>
    );
  };

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Viewer Preview</h3>
          <p className="text-xs text-gray-500">
            Reader viewer · presenter floats as a movable picture-in-picture
          </p>
        </div>
        <button
          type="button"
          onClick={() => setTheme((t) => (t === "night" ? "pdf" : "night"))}
          className="shrink-0 rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100 transition"
        >
          {theme === "night" ? "☾ Night" : "☀ PDF"}
        </button>
      </div>

      {canPreview && videoUrl ? (
        <div
          ref={frameRef}
          className="relative w-full overflow-hidden rounded-lg border border-gray-200"
          style={{
            aspectRatio: `${config.width} / ${config.height}`,
            backgroundColor: isText ? colors.bg : "#ffffff",
          }}
        >
          {renderDocument()}
          <video
            src={videoUrl}
            muted
            playsInline
            preload="metadata"
            className="absolute rounded-md border border-black/40 bg-black shadow-lg"
            style={{ ...pipStyle, objectFit: "cover", aspectRatio: "16 / 9" }}
            onLoadedMetadata={(e) => {
              e.currentTarget.currentTime = Math.min(
                1,
                e.currentTarget.duration || 1,
              );
            }}
          />
        </div>
      ) : (
        <div
          className="flex items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-xs text-gray-500"
          style={{ aspectRatio: `${config.width} / ${config.height}` }}
        >
          Upload a document and reference video to preview the viewer.
        </div>
      )}

      <p className="mt-2 text-xs text-gray-500">
        The theme and presenter position are adjustable live while watching;
        this is just a starting point.
      </p>
    </div>
  );
}
