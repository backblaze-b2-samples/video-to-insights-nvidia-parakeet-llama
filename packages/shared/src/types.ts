// Mirror of services/api/app/types/*.py — keep in lockstep.

export type JobStatusValue =
  | "queued"
  | "downloading"
  | "uploading_source"
  | "extracting_audio"
  | "transcribing"
  | "generating_insights"
  | "writing_manifest"
  | "done"
  | "done_no_analysis"
  | "failed"
  | "cancelled";

export type AnalysisStatus =
  | "pending"
  | "ok"
  | "skipped_no_api_key"
  | "failed_asr"
  | "failed_insights";

export interface JobProgress {
  stage: string;
  current: number;
  total: number;
}

export interface JobResult {
  source_key: string | null;
  transcript_key: string | null;
  insights_key: string | null;
  manifest_key: string | null;
}

export interface JobError {
  code: string;
  message: string;
}

export interface JobStatus {
  job_id: string;
  video_id: string;
  source_url: string;
  status: JobStatusValue;
  analysis_status: AnalysisStatus;
  analysis_message: string | null;
  progress: JobProgress;
  result: JobResult;
  error: JobError | null;
  created_at: string;
  updated_at: string;
  cancel_requested: boolean;
}

export interface SubmitRequest {
  youtube_url: string;
  segment_seconds?: number | null;
}

export interface SubmitResponse {
  job_id: string;
  status: JobStatusValue;
}

export interface Insight {
  index: number;
  title: string;
  summary: string;
  start_seconds: number;
  end_seconds: number;
  key_quotes: string[];
}

export interface ManifestV1 {
  schema_version: 1;
  video_id: string;
  source_url: string;
  source: { b2_key: string; duration_seconds: number | null; size_bytes: number | null };
  analysis_status: "ok" | "skipped_no_api_key" | "failed_asr" | "failed_insights";
  transcript_key: string | null;
  insights: Insight[];
  insights_key: string | null;
  models: { asr: string; insights: string };
  bucket: string;
  region: string;
  created_at: string;
}

/** Terminal job states — used by the poller to stop refetching. */
export const TERMINAL_STATUSES: ReadonlySet<JobStatusValue> = new Set([
  "done",
  "done_no_analysis",
  "failed",
  "cancelled",
]);

// --- Jobs index (mirror of app/types/jobs_index.py) ---

/** Manifest-level status — superset of "ok" plus the graceful-degradation modes. */
export type ManifestAnalysisStatus =
  | "ok"
  | "skipped_no_api_key"
  | "failed_asr"
  | "failed_insights";

export interface JobIndexEntry {
  video_id: string;
  job_id: string;
  source_url: string;
  duration_seconds: number | null;
  size_bytes: number | null;
  insights_count: number;
  analysis_status: ManifestAnalysisStatus;
  created_at: string;
  manifest_key: string;
  source_key: string;
}

export interface JobsIndex {
  schema_version: 1;
  updated_at: string;
  jobs: JobIndexEntry[];
}

/** API response for `GET /jobs?limit=&offset=`. */
export interface JobsIndexPage {
  jobs: JobIndexEntry[];
  total: number;
}

// --- Files (mirror of app/runtime/files.py) ---

export type FileKind =
  | "source"
  | "transcript"
  | "insights"
  | "manifest"
  | "jobs_index"
  | "other";

export interface FileObject {
  key: string;
  size: number;
  last_modified: string | null;
  etag: string;
  kind: FileKind;
}

export interface FilesPage {
  objects: FileObject[];
  next_token: string | null;
}
