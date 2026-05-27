"use client";

import { useRef } from "react";
import { useParams } from "next/navigation";
import { ArrowUpRight, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { JobStatusCard } from "@/components/jobs/job-status-card";
import { VideoPlayer } from "@/components/jobs/video-player";
import { InsightsPanel } from "@/components/jobs/insights-panel";
import { artifactUrl } from "@/lib/api-client";
import { useCancelJob, useJob } from "@/lib/queries";

// Job detail route. Layout mirrors the dashboard composition pattern:
// page header (title + meta + right-aligned action) over a 2/1 card
// grid. Polling and seek behavior are unchanged from prior rounds.
export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params?.id;
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const { data: job } = useJob(jobId ?? undefined);
  const cancel = useCancelJob();

  const isDone = job?.status === "done";
  const isDoneNoAnalysis = job?.status === "done_no_analysis";
  const isTerminal =
    isDone ||
    isDoneNoAnalysis ||
    job?.status === "failed" ||
    job?.status === "cancelled";
  const inFlight = job && !isTerminal;

  const seek = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      void videoRef.current.play().catch(() => {});
    }
  };

  const shortId = jobId ? jobId.slice(0, 8) : "";

  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="page-title">Job {shortId}</h1>
          {job ? (
            <p
              className="text-xs font-mono text-muted-foreground mt-1.5 truncate max-w-2xl"
              title={job.source_url}
            >
              {job.source_url}
            </p>
          ) : (
            <p className="text-xs font-mono text-muted-foreground mt-1.5">{jobId}</p>
          )}
        </div>
        {inFlight && job && !job.cancel_requested ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => cancel.mutate(job.job_id)}
            disabled={cancel.isPending}
            className="h-8"
          >
            <X className="h-3.5 w-3.5" />
            Cancel
          </Button>
        ) : null}
      </div>

      {job ? (
        <div className="animate-fade-in-up stagger-1">
          <JobStatusCard job={job} />
        </div>
      ) : null}

      {job && (isDone || isDoneNoAnalysis) ? (
        <section className="grid gap-4 lg:grid-cols-3 items-start">
          <div className="lg:col-span-2 animate-fade-in-up stagger-2 space-y-2">
            <Card>
              <CardContent className="p-0 overflow-hidden">
                <VideoPlayer ref={videoRef} jobId={job.job_id} />
              </CardContent>
            </Card>
            <a
              href={artifactUrl(job.job_id, "source")}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              View source video
              <ArrowUpRight className="h-3 w-3" />
            </a>
          </div>
          <aside className="animate-fade-in-up stagger-3">
            <Card>
              <CardHeader className="border-b border-border py-4 px-5">
                <CardTitle className="card-title">Insights</CardTitle>
              </CardHeader>
              <CardContent className="p-5">
                {isDone ? (
                  <InsightsPanel jobId={job.job_id} onSeek={seek} />
                ) : (
                  <div className="text-sm text-muted-foreground">
                    Analysis unavailable
                    {job.analysis_status === "skipped_no_api_key"
                      ? " — NVIDIA_API_KEY not set."
                      : job.analysis_status === "failed_asr"
                        ? " — transcription failed."
                        : job.analysis_status === "failed_insights"
                          ? " — insight extraction failed."
                          : "."}
                  </div>
                )}
              </CardContent>
            </Card>
          </aside>
        </section>
      ) : null}

      {job && isTerminal && job.status === "failed" ? (
        <div className="text-sm text-muted-foreground">
          The job failed before any video landed in B2. Submit a different URL
          from the New job page.
        </div>
      ) : null}
    </div>
  );
}
