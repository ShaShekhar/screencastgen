export interface UploadedFile {
  id: string;
  original_name: string;
  size_bytes: number;
  content_type: string;
}

export type PipelineType = "audio" | "highlight" | "lipsync" | "visualization";
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
  uploaded_file_id: string | null;
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

export interface LipsyncPageTime {
  page: number;
  seconds: number;
}

export interface LipsyncProgressData {
  event: "page_start" | "page_progress" | "page_done";
  page: number;
  completed: number;
  total: number;
  elapsed?: number;
  seconds?: number;
  page_times?: LipsyncPageTime[];
}

export interface ProgressEvent {
  job_id: string;
  status: string;
  phase: string;
  current: number;
  total: number;
  message: string;
  data?: LipsyncProgressData | null;
}

export interface AudioConfig {
  language: string;
  backend?: string;
  tts_server_url?: string;
}

export type HighlightFormat = "epub" | "mp4";

export interface HighlightConfig extends AudioConfig {
  format: HighlightFormat;
  voice_id?: string | null;
  ref_audio_file_id?: string | null;
  ref_text?: string | null;
  // Only used when format === "mp4". Output resolution in pixels.
  width: number;
  height: number;
}

export interface BundledVoice {
  id: string;
  name: string;
  language: string;
  description: string;
  ref_text: string;
  available: boolean;
}

export interface LipsyncPreset {
  id: string;
  name: string;
  language: string;
  description: string;
  ref_text: string;
  has_audio: boolean;
  available: boolean;
}

export interface LanguageOption {
  code: string;
  name: string;
}

export interface LipsyncConfig {
  preset_id?: string | null;
  ref_audio_file_id?: string | null;
  ref_video_file_id?: string | null;
  backend?: string;
  tts_server_url?: string;
  face_position: string;
  face_scale: number;
  latentsync_preset: string;
  font_size: number;
  width: number;
  height: number;
  fps: number;
  format?: "reader" | "mp4" | "epub";
}

export interface VisualizationConfig {
  prompt: string;
  provider: "manimgl" | "manimce";
  duration_seconds: number;
  width: number;
  height: number;
  fps: number;
  style: "clean" | "chalkboard" | "blueprint" | "minimal";
  audience_level: string;
  iteration_of_job_id?: string | null;
}

export interface ReaderWord {
  word: string;
  start: number;
  end: number;
}

export interface ReaderChunk {
  chunk_num: number;
  text: string;
  offset: number;
  pages: number[];
  words: ReaderWord[];
}

export interface ReaderPages {
  dir: string;
  image_width: number;
  files: Record<string, string>;
}

export interface ReaderManifest {
  version: number;
  title: string;
  language: string;
  source_type: string;
  source_file?: string | null;
  source_markdown?: string | null;
  duration: number;
  audio: string;
  presenter: string | null;
  pages: ReaderPages | null;
  chunks: ReaderChunk[];
}

export interface ReaderStatus {
  available: boolean;
  message: string;
}

export type EpubExportStatus = "running" | "done" | "failed" | null;

export interface EpubExportState {
  export_status: EpubExportStatus;
  export_output: string | null;
  export_error: string | null;
}

export interface JobCreateRequest {
  pipeline_type: PipelineType;
  uploaded_file_id?: string | null;
  audio_config?: AudioConfig;
  highlight_config?: HighlightConfig;
  lipsync_config?: LipsyncConfig;
  visualization_config?: VisualizationConfig;
}
