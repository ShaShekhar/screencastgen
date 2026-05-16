import { getLipsyncPreviewFrameUrl } from "../api/lipsync";
import { LipsyncConfig } from "../types";

interface Props {
  uploadedFileId?: string | null;
  config: LipsyncConfig;
}

export default function LipsyncPreviewFrame({ uploadedFileId, config }: Props) {
  const canPreview = !!uploadedFileId && !!config.ref_video_file_id;
  const previewUrl = canPreview
    ? getLipsyncPreviewFrameUrl(uploadedFileId, config)
    : null;

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-gray-800">Frame Preview</h3>
        <p className="text-xs text-gray-500">
          Shows the document with a representative face frame from the reference video.
        </p>
      </div>

      {previewUrl ? (
        <img
          src={previewUrl}
          alt="Lip-sync video frame preview"
          className="w-full rounded-lg border border-gray-200 bg-black"
        />
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
