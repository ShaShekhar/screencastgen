import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createJob } from "../api/jobs";
import FileUploader from "../components/FileUploader";
import LipsyncSettings from "../components/LipsyncSettings";
import PipelineSelector from "../components/PipelineSelector";
import VideoSettings from "../components/VideoSettings";
import VoiceSettings from "../components/VoiceSettings";
import {
  HighlightConfig,
  JobCreateRequest,
  LipsyncConfig,
  PipelineType,
  UploadedFile,
} from "../types";

const DEFAULT_HIGHLIGHT: HighlightConfig = {
  language: "en-US",
  format: "epub",
  voice_id: null,
  ref_audio_file_id: null,
  ref_text: null,
  width: 1280,
  height: 720,
};

const MP4_RESOLUTIONS = [
  { label: "720p (1280×720) — recommended", w: 1280, h: 720 },
  { label: "1080p (1920×1080) — larger file", w: 1920, h: 1080 },
];

const DEFAULT_LIPSYNC: LipsyncConfig = {
  ref_audio_file_id: "",
  ref_video_file_id: "",
  lipsync_provider: "auto",
  device: "auto",
  face_position: "bottom-right",
  face_scale: 0.22,
  latentsync_preset: "quality",
  font_size: 32,
  width: 1280,
  height: 720,
  fps: 24,
};

export default function NewJob() {
  const navigate = useNavigate();
  const [pipeline, setPipeline] = useState<PipelineType>("highlight");
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [highlightConfig, setHighlightConfig] =
    useState<HighlightConfig>(DEFAULT_HIGHLIGHT);
  const [lipsyncConfig, setLipsyncConfig] =
    useState<LipsyncConfig>(DEFAULT_LIPSYNC);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = () => {
    if (!uploadedFile) return false;
    if (pipeline === "lipsync") {
      return (
        lipsyncConfig.ref_audio_file_id !== "" &&
        lipsyncConfig.ref_video_file_id !== ""
      );
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!uploadedFile) return;
    setError(null);
    setSubmitting(true);

    const req: JobCreateRequest = {
      pipeline_type: pipeline,
      uploaded_file_id: uploadedFile.id,
    };

    if (pipeline === "highlight") {
      req.highlight_config = highlightConfig;
    } else {
      req.lipsync_config = lipsyncConfig;
    }

    try {
      const job = await createJob(req);
      navigate(`/jobs/${job.id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to create job";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Job</h1>

      {/* Step 1: Upload document */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          1. Upload Document
        </h2>
        <FileUploader
          accept=".pdf,.txt,.epub"
          label="Upload a PDF, TXT, or EPUB file"
          onUploaded={setUploadedFile}
        />
      </section>

      {/* Step 2: Select pipeline */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          2. Select Pipeline
        </h2>
        <PipelineSelector selected={pipeline} onChange={setPipeline} />
      </section>

      {/* Step 3: Configure */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          3. Settings
        </h2>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          {pipeline === "highlight" && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Output Format
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() =>
                      setHighlightConfig({ ...highlightConfig, format: "epub" })
                    }
                    className={`p-3 rounded-lg border-2 text-left transition ${
                      highlightConfig.format === "epub"
                        ? "border-indigo-600 bg-indigo-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <h4 className="font-semibold text-sm mb-0.5">EPUB</h4>
                    <p className="text-xs text-gray-500">
                      EPUB3 with embedded audio and word-level Media Overlay
                      highlighting. Plays in Apple Books, Thorium, Readium.
                    </p>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setHighlightConfig({ ...highlightConfig, format: "mp4" })
                    }
                    className={`p-3 rounded-lg border-2 text-left transition ${
                      highlightConfig.format === "mp4"
                        ? "border-indigo-600 bg-indigo-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <h4 className="font-semibold text-sm mb-0.5">MP4 Video</h4>
                    <p className="text-xs text-gray-500">
                      Rendered video with PDF page images and word-by-word
                      highlighted text.
                    </p>
                  </button>
                </div>
              </div>
              <VoiceSettings
                config={highlightConfig}
                onChange={(c) =>
                  setHighlightConfig({ ...highlightConfig, ...c })
                }
                uploadedFileId={uploadedFile?.id}
              />
              {highlightConfig.format === "mp4" && (
                <>
                  <hr />
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Video Resolution
                    </label>
                    <select
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                      value={`${highlightConfig.width}x${highlightConfig.height}`}
                      onChange={(e) => {
                        const r = MP4_RESOLUTIONS.find(
                          (r) => `${r.w}x${r.h}` === e.target.value,
                        );
                        if (r)
                          setHighlightConfig({
                            ...highlightConfig,
                            width: r.w,
                            height: r.h,
                          });
                      }}
                    >
                      {MP4_RESOLUTIONS.map((r) => (
                        <option
                          key={`${r.w}x${r.h}`}
                          value={`${r.w}x${r.h}`}
                        >
                          {r.label}
                        </option>
                      ))}
                    </select>
                    <p className="mt-1 text-xs text-gray-500">
                      Higher resolution produces sharper PDF pages but a
                      larger output file. Frame rate is fixed at 24 fps.
                    </p>
                  </div>
                </>
              )}
            </div>
          )}

          {pipeline === "lipsync" && (
            <div className="space-y-6">
              <LipsyncSettings
                config={lipsyncConfig}
                onChange={setLipsyncConfig}
              />
              <hr />
              <VideoSettings
                config={lipsyncConfig}
                onChange={(c) =>
                  setLipsyncConfig({ ...lipsyncConfig, ...c })
                }
              />
            </div>
          )}
        </div>
      </section>

      {/* Submit */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">
          {error}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit() || submitting}
        className={`w-full py-3 rounded-xl text-sm font-semibold transition ${
          canSubmit() && !submitting
            ? "bg-indigo-600 text-white hover:bg-indigo-700"
            : "bg-gray-200 text-gray-500 cursor-not-allowed"
        }`}
      >
        {submitting ? "Creating..." : "Create Job"}
      </button>
    </div>
  );
}
