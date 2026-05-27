"use client";

import { useMemo } from "react";
import { Film, HardDrive, Mic, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useJobsIndex } from "@/lib/queries";
import { humanizeBytes } from "@/lib/utils";
import type {
  JobIndexEntry,
  ManifestAnalysisStatus,
} from "@video-to-insights-pipeline/shared";

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

// Successful analysis statuses — used to filter "Videos processed" count.
const SUCCESS_STATUSES: Set<ManifestAnalysisStatus> = new Set(["ok"]);

function fmtDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0m";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function computeStats(jobs: JobIndexEntry[]) {
  const now = Date.now();
  let videosProcessed = 0;
  let weeklyCount = 0;
  let totalBytes = 0;
  let totalDuration = 0;
  let totalInsights = 0;
  let videosWithInsights = 0;
  for (const job of jobs) {
    if (SUCCESS_STATUSES.has(job.analysis_status)) videosProcessed += 1;
    if (now - new Date(job.created_at).getTime() < SEVEN_DAYS_MS) weeklyCount += 1;
    if (job.size_bytes) totalBytes += job.size_bytes;
    if (job.duration_seconds) totalDuration += job.duration_seconds;
    if (job.insights_count > 0) {
      totalInsights += job.insights_count;
      videosWithInsights += 1;
    }
  }
  return {
    videosProcessed,
    weeklyCount,
    totalBytes,
    totalDuration,
    totalInsights,
    videosWithInsights,
    fileCount: jobs.length,
  };
}

export function StatsCards() {
  // Pull a generous slice — index is small (one entry per video) so we
  // can compute every stat client-side without a dedicated endpoint.
  const { data, isLoading, error, refetch } = useJobsIndex({ limit: 1000, offset: 0 });

  const stats = useMemo(() => computeStats(data?.jobs ?? []), [data]);

  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  const avgInsights = stats.videosWithInsights
    ? Math.round(stats.totalInsights / stats.videosWithInsights)
    : 0;

  const cards = [
    {
      title: "Videos processed",
      value: stats.videosProcessed,
      sub: `+${stats.weeklyCount} this week`,
      icon: Film,
    },
    {
      title: "Source in B2",
      value: humanizeBytes(stats.totalBytes),
      sub: `across ${stats.fileCount} ${stats.fileCount === 1 ? "video" : "videos"}`,
      icon: HardDrive,
    },
    {
      title: "Transcribed",
      value: fmtDuration(stats.totalDuration),
      sub: "audio processed",
      icon: Mic,
    },
    {
      title: "Insights extracted",
      value: stats.totalInsights,
      sub: `avg ${avgInsights} per video`,
      icon: Sparkles,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, i) => (
        <Card
          key={card.title}
          className={`card-hover animate-fade-in-up stagger-${i + 1}`}
        >
          <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground">
              {card.title}
            </CardTitle>
            <div className="stat-icon-wrap">
              <card.icon className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent className="pb-5 px-4">
            {isLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <>
                <div className="stat-value">{card.value}</div>
                <div className="text-xs text-muted-foreground mt-1">{card.sub}</div>
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
