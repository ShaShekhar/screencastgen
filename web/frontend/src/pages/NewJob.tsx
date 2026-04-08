import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createJob } from "../api/jobs";
import FileUploader from "../components/FileUploader";
import LipsyncSettings from "../components/LipsyncSettings";
import PipelineSelector from "../components/PipelineSelector";
import VideoSettings from "../components/VideoSettings";
import VoiceSettings from "../components/VoiceSettings";
import {
  AudioConfig,
  HighlightConfig,
  JobCreateRequest,
  LipsyncConfig,
  PipelineType,
  UploadedFile,
} from "../types";

const DEFAULT_AUDIO: AudioConfig = {
  language: "en-US",
  aligner: "whisperx",
};

const DEFAULT_HIGHLIGHT: HighlightConfig = {
  ...DEFAULT_AUDIO,
  font_size: 32,
  width: 1280,
  height: 720,
  fps: 24,
};

const DEFAULT_LIPSYNC: LipsyncConfig = {
  ref_audio_file_id: "",
  ref_video_file_id: "",
  aligner: "whisperx",
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
  const [pipeline, setPipeline] = useState<PipelineType>("audio");
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [audioConfig, setAudioConfig] = useState<AudioConfig>(DEFAULT_AUDIO);
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

    if (pipeline === "audio") {
      req.audio_config = audioConfig;
    } else if (pipeline === "highlight") {
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

      {/* Step 1: Upload PDF */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          1. Upload PDF
        </h2>
        <FileUploader
          accept=".pdf"
          label="Upload your PDF file"
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
          {pipeline === "audio" && (
            <VoiceSettings config={audioConfig} onChange={setAudioConfig} />
          )}

          {pipeline === "highlight" && (
            <div className="space-y-6">
              <VoiceSettings
                config={highlightConfig}
                showAligner
                onChange={(c) =>
                  setHighlightConfig({ ...highlightConfig, ...c })
                }
              />
              <hr />
              <VideoSettings
                config={highlightConfig}
                onChange={(c) =>
                  setHighlightConfig({ ...highlightConfig, ...c })
                }
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
