"use client";

import Link from "next/link";
import { ArrowRight, Inbox } from "lucide-react";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useJobsIndex } from "@/lib/queries";
import { formatDate } from "@/lib/utils";
import type { ManifestAnalysisStatus } from "@video-to-insights-pipeline/shared";

// Short "host + path" rendering for long YouTube URLs so the column
// stays one line in the fixed-layout table.
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

// Map analysis_status → dot color + label. Three buckets: success, neutral
// (intentionally no analysis), and partial (asr or insights failed).
const STATUS_DOT: Record<ManifestAnalysisStatus, string> = {
  ok: "bg-[var(--success)]",
  skipped_no_api_key: "bg-muted-foreground",
  failed_asr: "bg-[var(--attention)]",
  failed_insights: "bg-[var(--attention)]",
};

const STATUS_LABEL: Record<ManifestAnalysisStatus, string> = {
  ok: "Done",
  skipped_no_api_key: "No analysis",
  failed_asr: "Partial",
  failed_insights: "Partial",
};

export function RecentVideosTable() {
  // 10 most recent — index is naturally sorted newest-first.
  const { data, isLoading, error, refetch } = useJobsIndex({ limit: 10, offset: 0 });
  const jobs = data?.jobs ?? [];

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Recent videos</CardTitle>
        <CardAction className="self-center">
          <Link
            href="/files"
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            View files
            <ArrowRight className="h-3 w-3" />
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : jobs.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No videos yet"
            description="Submit a YouTube URL on the New job page."
          />
        ) : (
          <Table className="table-fixed">
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="w-[34%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Source
                </TableHead>
                <TableHead className="w-[14%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Duration
                </TableHead>
                <TableHead className="w-[14%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Insights
                </TableHead>
                <TableHead className="w-[22%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Date
                </TableHead>
                <TableHead className="w-[16%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Status
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.job_id} className="table-row-hover">
                  <TableCell className="font-medium">
                    <Link
                      href={`/jobs/${job.job_id}`}
                      className="block truncate font-mono text-xs hover:text-foreground"
                      title={job.source_url}
                    >
                      {shortUrl(job.source_url)}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground tabular-nums whitespace-nowrap">
                    {fmtDuration(job.duration_seconds)}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground tabular-nums whitespace-nowrap">
                    {job.insights_count}
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatDate(job.created_at)}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[job.analysis_status]}`}
                      />
                      {STATUS_LABEL[job.analysis_status]}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
