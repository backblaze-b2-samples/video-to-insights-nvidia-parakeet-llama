import type {
  FilesPage,
  JobIndexEntry,
  JobStatus,
  JobsIndexPage,
  SubmitRequest,
  SubmitResponse,
} from "@video-to-insights-pipeline/shared";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Typed API error with HTTP status code for caller-side branching. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True for 408, 429, 500, 502, 503, 504 — worth retrying. */
  get isRetryable(): boolean {
    return [408, 429, 500, 502, 503, 504].includes(this.status);
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("Network error — check your connection", 0);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // 422 errors carry a {code, message} dict per app/runtime/jobs.py
    const detail = body.detail;
    let msg: string;
    if (detail && typeof detail === "object" && "message" in detail) {
      msg = String((detail as { message: string }).message);
    } else if (typeof detail === "string") {
      msg = detail;
    } else {
      msg = `API error: ${res.status}`;
    }
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

export async function getHealth() {
  return apiFetch<{ status: string; b2_connected: boolean; nvidia_configured: boolean }>(
    "/health",
  );
}

export async function submitJob(payload: SubmitRequest) {
  return apiFetch<SubmitResponse>("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getJob(jobId: string) {
  return apiFetch<JobStatus>(`/jobs/${encodeURIComponent(jobId)}`);
}

export async function cancelJob(jobId: string) {
  return apiFetch<JobStatus>(`/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
}

/** Build URL to the API redirect endpoint for a presigned artifact. */
export function artifactUrl(
  jobId: string,
  kind: "source" | "manifest" | "transcript" | "insights",
): string {
  return `${API_BASE}/jobs/${encodeURIComponent(jobId)}/${kind}`;
}

export async function getLatestJob() {
  return apiFetch<JobIndexEntry | null>("/jobs/latest");
}

export async function getJobsIndex(params: { limit?: number; offset?: number } = {}) {
  const q = new URLSearchParams();
  if (params.limit !== undefined) q.set("limit", String(params.limit));
  if (params.offset !== undefined) q.set("offset", String(params.offset));
  const qs = q.toString();
  return apiFetch<JobsIndexPage>(`/jobs${qs ? `?${qs}` : ""}`);
}

export async function getFiles(params: { continuationToken?: string; maxKeys?: number } = {}) {
  const q = new URLSearchParams();
  if (params.continuationToken)
    q.set("continuation_token", params.continuationToken);
  if (params.maxKeys !== undefined) q.set("max_keys", String(params.maxKeys));
  const qs = q.toString();
  return apiFetch<FilesPage>(`/files${qs ? `?${qs}` : ""}`);
}
