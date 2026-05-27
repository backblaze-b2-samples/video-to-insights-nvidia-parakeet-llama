"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  cancelJob,
  getFiles,
  getHealth,
  getJob,
  getJobsIndex,
  getLatestJob,
  submitJob,
} from "@/lib/api-client";
import {
  type JobStatus,
  TERMINAL_STATUSES,
} from "@video-to-insights-pipeline/shared";

export const qk = {
  all: ["v2i"] as const,
  health: () => [...qk.all, "health"] as const,
  job: (jobId: string) => [...qk.all, "job", jobId] as const,
  latestJob: () => [...qk.all, "latest-job"] as const,
  jobsIndex: (limit: number, offset: number) =>
    [...qk.all, "jobs-index", limit, offset] as const,
  files: (token: string | undefined) =>
    [...qk.all, "files", token ?? "first"] as const,
};

export function useHealth() {
  return useQuery({ queryKey: qk.health(), queryFn: getHealth });
}

/** Poll a job while it's running. Stops polling once it hits a terminal state. */
export function useJob(jobId: string | undefined) {
  return useQuery<JobStatus, ApiError>({
    queryKey: qk.job(jobId ?? ""),
    queryFn: () => getJob(jobId as string),
    enabled: !!jobId,
    // Refetch every 1.5s while the job is still moving — TanStack accepts
    // a function form here that gets the latest data and returns the next
    // interval (or false to stop).
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 1500;
      return TERMINAL_STATUSES.has(data.status) ? false : 1500;
    },
  });
}

export function useSubmitJob() {
  return useMutation({ mutationFn: submitJob });
}

export function useCancelJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cancelJob,
    onSuccess: (data) => {
      qc.setQueryData(qk.job(data.job_id), data);
    },
  });
}

/** Dashboard hero — most recent successful job, fetched once per mount/focus. */
export function useLatestJob() {
  return useQuery({
    queryKey: qk.latestJob(),
    queryFn: getLatestJob,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

/** Paginated index for the "Previous videos" table. */
export function useJobsIndex({ limit = 10, offset = 0 }: { limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: qk.jobsIndex(limit, offset),
    queryFn: () => getJobsIndex({ limit, offset }),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

/** Paginated B2 listing of the pipeline's prefix — backs the /files page. */
export function useFiles(continuationToken?: string) {
  return useQuery({
    queryKey: qk.files(continuationToken),
    queryFn: () => getFiles({ continuationToken }),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}
