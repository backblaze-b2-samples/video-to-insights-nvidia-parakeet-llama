"use client";

import Link from "next/link";
import { ArrowUpRight, Video } from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useLatestJob } from "@/lib/queries";

// "Last processed video" card. Compact summary — duration, insight count,
// and a deep link into the job detail page (where the video is playable).
function shortUrl(raw: string): string {
  try {
    const u = new URL(raw);
    const path = u.pathname === "/" ? "" : u.pathname;
    return `${u.host}${path}${u.search}`;
  } catch {
    return raw;
  }
}

function fmtDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function LastProcessedCard() {
  const { data, isLoading, error, refetch } = useLatestJob();

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Last processed</CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : !data ? (
          <EmptyState
            icon={Video}
            title="No videos yet"
            description="Submit a YouTube URL on the New job page to get started."
          />
        ) : (
          <div className="space-y-4">
            <div className="space-y-1">
              <div
                className="font-mono text-xs text-foreground truncate"
                title={data.source_url}
              >
                {shortUrl(data.source_url)}
              </div>
              <div className="text-xs text-muted-foreground">
                {data.video_id}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Duration
                </div>
                <div className="font-mono tabular-nums">
                  {fmtDuration(data.duration_seconds)}
                </div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Insights
                </div>
                <div className="font-mono tabular-nums">{data.insights_count}</div>
              </div>
            </div>
            <Link
              href={`/jobs/${data.job_id}`}
              className="inline-flex items-center gap-1 text-xs font-medium text-foreground hover:text-primary transition-colors"
            >
              View
              <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
