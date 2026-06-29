import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createJob } from "../api/jobs";
import FileUploader from "../components/FileUploader";
import LipsyncPreviewFrame from "../components/LipsyncPreviewFrame";
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

const DEFAULT_LIPSYNC: LipsyncConfig = {
  preset_id: null,
  ref_audio_file_id: null,
  ref_video_file_id: null,
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
  const [pipeline, setPipeline] = useState<PipelineType>("lipsync");
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
      return !!lipsyncConfig.preset_id || !!lipsyncConfig.ref_video_file_id;
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
      req.highlight_config = { ...highlightConfig, format: "epub" };
    } else if (pipeline === "lipsync") {
      req.lipsync_config = lipsyncConfig;
    }

    try {
      await createJob(req);
      navigate("/");
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

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          1. Upload Document
        </h2>
        <FileUploader
          accept=".pdf,.txt,.md,.markdown,.mdown"
          label="Upload a PDF, TXT, or Markdown file"
          onUploaded={setUploadedFile}
          showPreview
        />
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          2. Select Pipeline
        </h2>
        <PipelineSelector selected={pipeline} onChange={setPipeline} />
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          3. Settings
        </h2>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          {pipeline === "highlight" && (
            <div className="space-y-6">
              <VoiceSettings
                config={highlightConfig}
                onChange={(c) =>
                  setHighlightConfig({ ...highlightConfig, ...c, format: "epub" })
                }
                uploadedFileId={uploadedFile?.id}
              />
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
              <LipsyncPreviewFrame
                uploadedFile={uploadedFile}
                config={lipsyncConfig}
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
