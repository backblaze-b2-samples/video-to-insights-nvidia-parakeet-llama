"use client";

import { Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCancelJob } from "@/lib/queries";
import type { JobStatus } from "@video-to-insights-pipeline/shared";

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  downloading: "Downloading from YouTube",
  uploading_source: "Uploading to Backblaze B2",
  extracting_audio: "Extracting audio",
  transcribing: "Transcribing (Parakeet)",
  generating_insights: "Generating insights (Llama-3.3)",
  writing_manifest: "Writing manifest",
  done: "Done",
  done_no_analysis: "Done (video only)",
  failed: "Failed",
  cancelled: "Cancelled",
};

interface JobStatusCardProps {
  job: JobStatus;
}

export function JobStatusCard({ job }: JobStatusCardProps) {
  const cancel = useCancelJob();
  const inFlight =
    job.status !== "done" &&
    job.status !== "done_no_analysis" &&
    job.status !== "failed" &&
    job.status !== "cancelled";

  return (
    <div className="rounded-lg border bg-card p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {inFlight && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          <span className="text-sm font-medium">{STAGE_LABELS[job.status] ?? job.status}</span>
        </div>
        {inFlight && !job.cancel_requested ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => cancel.mutate(job.job_id)}
            disabled={cancel.isPending}
          >
            <X className="h-3.5 w-3.5" />
            Cancel
          </Button>
        ) : null}
      </div>
      <div className="text-xs text-muted-foreground truncate">{job.source_url}</div>
      {job.error ? (
        <div className="text-xs text-destructive">
          <span className="font-mono">{job.error.code}</span> — {job.error.message}
        </div>
      ) : null}
      {job.cancel_requested && inFlight ? (
        <div className="text-xs text-muted-foreground italic">
          Cancellation requested; finishing current stage.
        </div>
      ) : null}
    </div>
  );
}
