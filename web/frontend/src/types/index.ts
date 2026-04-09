export interface UploadedFile {
  id: string;
  original_name: string;
  size_bytes: number;
  content_type: string;
}

export type PipelineType = "audio" | "highlight" | "lipsync";
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface Job {
  id: string;
  pipeline_type: PipelineType;
  status: JobStatus;
  progress_current: number;
  progress_total: number;
  progress_phase: string;
  error_message: string | null;
  config_json: Record<string, unknown>;
  uploaded_file_id: string;
  ref_audio_file_id: string | null;
  ref_video_file_id: string | null;
  output_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
}

export interface ProgressEvent {
  job_id: string;
  status: string;
  phase: string;
  current: number;
  total: number;
  message: string;
}

export interface AudioConfig {
  language: string;
  backend?: string;
  tts_server_url?: string;
  aligner?: string;
}

export interface HighlightConfig extends AudioConfig {
  voice_id?: string | null;
  ref_audio_file_id?: string | null;
  ref_text?: string | null;
  font_size: number;
  width: number;
  height: number;
  fps: number;
}

export interface BundledVoice {
  id: string;
  name: string;
  language: string;
  description: string;
  ref_text: string;
  available: boolean;
}

export interface LanguageOption {
  code: string;
  name: string;
}

export interface LipsyncConfig {
  ref_audio_file_id: string;
  ref_video_file_id: string;
  ref_text?: string;
  backend?: string;
  aligner?: string;
  lipsync_provider?: string;
  device: string;
  tts_server_url?: string;
  face_position: string;
  face_scale: number;
  latentsync_preset: string;
  font_size: number;
  width: number;
  height: number;
  fps: number;
}

export interface JobCreateRequest {
  pipeline_type: PipelineType;
  uploaded_file_id: string;
  audio_config?: AudioConfig;
  highlight_config?: HighlightConfig;
  lipsync_config?: LipsyncConfig;
}
