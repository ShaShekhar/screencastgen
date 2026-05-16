import { ChangeEvent, DragEvent, useCallback, useRef, useState } from "react";
import { getUploadPreviewUrl, uploadFile } from "../api/uploads";
import { UploadedFile } from "../types";

interface Props {
  accept: string;
  label: string;
  onUploaded: (file: UploadedFile) => void;
  showPreview?: boolean;
}

export default function FileUploader({
  accept,
  label,
  onUploaded,
  showPreview = false,
}: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [fileName, setFileName] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setUploading(true);
      setFileName(file.name);
      setUploadedFile(null);
      setProgress(0);
      try {
        const uploaded = await uploadFile(file, setProgress);
        setUploadedFile(uploaded);
        onUploaded(uploaded);
      } catch (e: unknown) {
        const msg =
          e instanceof Error ? e.message : "Upload failed";
        setError(msg);
        setFileName(null);
        setUploadedFile(null);
      } finally {
        setUploading(false);
      }
    },
    [onUploaded]
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition ${
        dragOver
          ? "border-indigo-500 bg-indigo-50"
          : "border-gray-300 hover:border-gray-400"
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={onInputChange}
      />

      {uploading ? (
        <div>
          <p className="text-sm text-gray-600 mb-2">
            Uploading {fileName}...
          </p>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-indigo-600 h-2 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1">{progress}%</p>
        </div>
      ) : fileName ? (
        <div className="space-y-2">
          <p className="text-sm text-green-700 font-medium">{fileName}</p>
          {showPreview && uploadedFile && (
            <a
              href={getUploadPreviewUrl(uploadedFile.id)}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center rounded-lg border border-green-200 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-50 transition"
            >
              Open preview
            </a>
          )}
        </div>
      ) : (
        <div>
          <p className="text-sm text-gray-600 font-medium">{label}</p>
          <p className="text-xs text-gray-400 mt-1">
            Drag & drop or click to browse
          </p>
        </div>
      )}

      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
    </div>
  );
}
