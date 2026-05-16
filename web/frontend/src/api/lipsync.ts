import { LipsyncConfig } from "../types";

export function getLipsyncPreviewFrameUrl(
  uploadedFileId: string,
  config: LipsyncConfig
): string {
  const params = new URLSearchParams({
    uploaded_file_id: uploadedFileId,
    ref_video_file_id: config.ref_video_file_id,
    face_position: config.face_position,
    face_scale: String(config.face_scale),
    width: String(config.width),
    height: String(config.height),
    font_size: String(config.font_size),
  });

  return `/api/lipsync/preview-frame?${params.toString()}`;
}
