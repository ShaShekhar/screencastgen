import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { getUploadPreviewUrl } from "../api/uploads";
import type { LipsyncConfig, UploadedFile } from "../types";

interface Props {
  uploadedFile?: UploadedFile | null;
  config: LipsyncConfig;
}

interface Size {
  width: number;
  height: number;
}

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

const OVERLAY_POSITIONS = new Set([
  "top-left",
  "top-right",
  "bottom-left",
  "bottom-right",
]);

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

function calculateLayout(config: LipsyncConfig, videoSize: Size): {
  face: Box;
  text: Box;
} {
  const frameW = config.width;
  const frameH = config.height;
  const margin = Math.max(16, Math.floor(Math.min(frameW, frameH) * 0.03));

  if (OVERLAY_POSITIONS.has(config.face_position)) {
    const srcFaceW = Math.max(videoSize.width, 1);
    const srcFaceH = Math.max(videoSize.height, 1);
    let faceW = Math.max(1, Math.floor(frameW * clamp(config.face_scale, 0.1, 0.9)));
    let faceH = Math.max(1, Math.floor((srcFaceH * faceW) / srcFaceW));

    if (faceH > frameH - margin * 2) {
      faceH = Math.max(1, frameH - margin * 2);
      faceW = Math.max(1, Math.floor((srcFaceW * faceH) / srcFaceH));
    }

    const railW = Math.min(frameW - 1, faceW + margin * 2);
    const textW = Math.max(1, frameW - railW);
    const faceX = config.face_position.endsWith("left")
      ? margin
      : frameW - faceW - margin;
    const faceY = config.face_position.startsWith("top")
      ? margin
      : frameH - faceH - margin;
    const textX = config.face_position.endsWith("left") ? frameW - textW : 0;

    return {
      face: { x: faceX, y: faceY, width: faceW, height: faceH },
      text: { x: textX, y: 0, width: textW, height: frameH },
    };
  }

  if (config.face_position === "left") {
    return {
      face: { x: 0, y: 0, width: Math.floor(frameW / 2), height: frameH },
      text: {
        x: Math.floor(frameW / 2),
        y: 0,
        width: Math.floor(frameW / 2),
        height: frameH,
      },
    };
  }

  if (config.face_position === "right") {
    return {
      face: {
        x: Math.floor(frameW / 2),
        y: 0,
        width: Math.floor(frameW / 2),
        height: frameH,
      },
      text: { x: 0, y: 0, width: Math.floor(frameW / 2), height: frameH },
    };
  }

  const faceW = Math.floor(frameW / 2);
  const faceH = Math.floor(frameH / 2);
  return {
    face: { x: Math.floor((frameW - faceW) / 2), y: 0, width: faceW, height: faceH },
    text: { x: 0, y: faceH, width: frameW, height: Math.max(1, frameH - faceH) },
  };
}

function boxStyle(box: Box, frame: Size): CSSProperties {
  return {
    left: `${(box.x / frame.width) * 100}%`,
    top: `${(box.y / frame.height) * 100}%`,
    width: `${(box.width / frame.width) * 100}%`,
    height: `${(box.height / frame.height) * 100}%`,
  };
}

export default function LipsyncPreviewFrame({ uploadedFile, config }: Props) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [videoSize, setVideoSize] = useState<Size>({ width: 16, height: 9 });
  const [frameDisplayWidth, setFrameDisplayWidth] = useState(0);
  const [documentText, setDocumentText] = useState<string | null>(null);
  const canPreview = !!uploadedFile && !!config.ref_video_file_id;
  const documentUrl = uploadedFile ? getUploadPreviewUrl(uploadedFile.id) : null;
  const videoUrl = config.ref_video_file_id
    ? getUploadPreviewUrl(config.ref_video_file_id)
    : null;

  const layout = useMemo(
    () => calculateLayout(config, videoSize),
    [config, videoSize],
  );

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

  const frameSize = { width: config.width, height: config.height };
  const previewFontSize = Math.max(
    10,
    config.font_size * (frameDisplayWidth ? frameDisplayWidth / config.width : 0.5),
  );

  const renderDocument = () => {
    if (!uploadedFile || !documentUrl) return null;

    if (isTextDocument(uploadedFile)) {
      return (
        <div
          className="h-full overflow-hidden whitespace-pre-wrap break-words p-4 leading-relaxed text-white"
          style={{ fontSize: previewFontSize }}
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
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-gray-800">Frame Preview</h3>
        <p className="text-xs text-gray-500">
          {config.width}x{config.height} at {config.fps} fps
        </p>
      </div>

      {canPreview && videoUrl ? (
        <div
          ref={frameRef}
          className="relative w-full overflow-hidden rounded-lg border border-gray-200 bg-[#1e1e1e]"
          style={{ aspectRatio: `${config.width} / ${config.height}` }}
        >
          <div
            className="absolute overflow-hidden bg-[#1e1e1e]"
            style={boxStyle(layout.text, frameSize)}
          >
            {renderDocument()}
          </div>
          <video
            src={videoUrl}
            muted
            playsInline
            preload="metadata"
            className="absolute bg-black"
            style={{
              ...boxStyle(layout.face, frameSize),
              objectFit: OVERLAY_POSITIONS.has(config.face_position)
                ? "contain"
                : "fill",
            }}
            onLoadedMetadata={(e) => {
              setVideoSize({
                width: e.currentTarget.videoWidth || 16,
                height: e.currentTarget.videoHeight || 9,
              });
              e.currentTarget.currentTime = Math.min(1, e.currentTarget.duration || 1);
            }}
          />
        </div>
      ) : (
        <div
          className="flex items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-xs text-gray-500"
          style={{ aspectRatio: `${config.width} / ${config.height}` }}
        >
          Upload a document and reference video to preview the frame.
        </div>
      )}
    </div>
  );
}
