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
  VisualizationConfig,
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

const DEFAULT_VISUALIZATION: VisualizationConfig = {
  prompt: "",
  provider: "manimgl",
  duration_seconds: 30,
  width: 1280,
  height: 720,
  fps: 24,
  style: "clean",
  audience_level: "general",
  iteration_of_job_id: null,
};

const VISUALIZATION_RESOLUTIONS = [
  { label: "1280x720 (HD)", w: 1280, h: 720 },
  { label: "1920x1080 (Full HD)", w: 1920, h: 1080 },
  { label: "854x480 (SD)", w: 854, h: 480 },
];

export default function NewJob() {
  const navigate = useNavigate();
  const [pipeline, setPipeline] = useState<PipelineType>("highlight");
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [highlightConfig, setHighlightConfig] =
    useState<HighlightConfig>(DEFAULT_HIGHLIGHT);
  const [lipsyncConfig, setLipsyncConfig] =
    useState<LipsyncConfig>(DEFAULT_LIPSYNC);
  const [visualizationConfig, setVisualizationConfig] =
    useState<VisualizationConfig>(DEFAULT_VISUALIZATION);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = () => {
    if (pipeline === "visualization") {
      return visualizationConfig.prompt.trim().length > 0;
    }
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
    if (pipeline !== "visualization" && !uploadedFile) return;
    setError(null);
    setSubmitting(true);

    const req: JobCreateRequest = {
      pipeline_type: pipeline,
      uploaded_file_id: pipeline === "visualization" ? null : uploadedFile?.id,
    };

    if (pipeline === "highlight") {
      req.highlight_config = { ...highlightConfig, format: "epub" };
    } else if (pipeline === "lipsync") {
      req.lipsync_config = lipsyncConfig;
    } else if (pipeline === "visualization") {
      req.visualization_config = visualizationConfig;
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

      {pipeline !== "visualization" && (
        <section className="mb-8">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            1. Upload Document
          </h2>
          <FileUploader
            accept=".pdf,.txt,.epub"
            label="Upload a PDF, TXT, or EPUB file"
            onUploaded={setUploadedFile}
            showPreview
          />
        </section>
      )}

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          {pipeline === "visualization" ? "1" : "2"}. Select Pipeline
        </h2>
        <PipelineSelector selected={pipeline} onChange={setPipeline} />
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          {pipeline === "visualization" ? "2" : "3"}. Settings
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
            </div>
          )}

          {pipeline === "visualization" && (
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Concept Prompt
                </label>
                <textarea
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm min-h-32"
                  value={visualizationConfig.prompt}
                  onChange={(e) =>
                    setVisualizationConfig({
                      ...visualizationConfig,
                      prompt: e.target.value,
                    })
                  }
                  placeholder="Explain the derivative as the slope of a moving tangent line"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Renderer
                  </label>
                  <select
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    value={visualizationConfig.provider}
                    onChange={(e) =>
                      setVisualizationConfig({
                        ...visualizationConfig,
                        provider: e.target.value as VisualizationConfig["provider"],
                      })
                    }
                  >
                    <option value="manimgl">ManimGL</option>
                    <option value="manimce">Manim Community (stub)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Style
                  </label>
                  <select
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    value={visualizationConfig.style}
                    onChange={(e) =>
                      setVisualizationConfig({
                        ...visualizationConfig,
                        style: e.target.value as VisualizationConfig["style"],
                      })
                    }
                  >
                    <option value="clean">Clean</option>
                    <option value="chalkboard">Chalkboard</option>
                    <option value="blueprint">Blueprint</option>
                    <option value="minimal">Minimal</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Audience Level
                </label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  value={visualizationConfig.audience_level}
                  onChange={(e) =>
                    setVisualizationConfig({
                      ...visualizationConfig,
                      audience_level: e.target.value,
                    })
                  }
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Resolution
                  </label>
                  <select
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    value={`${visualizationConfig.width}x${visualizationConfig.height}`}
                    onChange={(e) => {
                      const r = VISUALIZATION_RESOLUTIONS.find(
                        (r) => `${r.w}x${r.h}` === e.target.value,
                      );
                      if (r)
                        setVisualizationConfig({
                          ...visualizationConfig,
                          width: r.w,
                          height: r.h,
                        });
                    }}
                  >
                    {VISUALIZATION_RESOLUTIONS.map((r) => (
                      <option key={`${r.w}x${r.h}`} value={`${r.w}x${r.h}`}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    FPS
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    value={visualizationConfig.fps}
                    onChange={(e) =>
                      setVisualizationConfig({
                        ...visualizationConfig,
                        fps: parseInt(e.target.value) || 24,
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Duration
                  </label>
                  <input
                    type="number"
                    min={3}
                    max={600}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    value={visualizationConfig.duration_seconds}
                    onChange={(e) =>
                      setVisualizationConfig({
                        ...visualizationConfig,
                        duration_seconds: parseInt(e.target.value) || 30,
                      })
                    }
                  />
                </div>
              </div>
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
