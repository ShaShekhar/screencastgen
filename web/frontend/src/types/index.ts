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
  voice: string;
  language: string;
  encoding: string;
}

export interface HighlightConfig extends AudioConfig {
  font_size: number;
  width: number;
  height: number;
  fps: number;
}

export interface LipsyncConfig {
  ref_audio_file_id: string;
  ref_video_file_id: string;
  ref_text?: string;
  device: string;
  face_position: string;
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
