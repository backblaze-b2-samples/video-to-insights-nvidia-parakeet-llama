"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { BarChart3 } from "lucide-react";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobsIndex } from "@/lib/queries";

const chartConfig = {
  jobs: {
    label: "Jobs",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig;

// Round `d` down to local midnight for stable per-day grouping.
function dayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function ActivityChart() {
  const { data, isLoading, error, refetch } = useJobsIndex({ limit: 1000, offset: 0 });

  // Bucket the trailing 7 days, including today. Days with zero jobs
  // still render so the bar chart shows a continuous timeline.
  const series = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const buckets = new Map<string, { label: string; jobs: number }>();
    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date(today);
      d.setDate(today.getDate() - i);
      buckets.set(dayKey(d), {
        label: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
        jobs: 0,
      });
    }
    for (const job of data?.jobs ?? []) {
      const key = dayKey(new Date(job.created_at));
      const bucket = buckets.get(key);
      if (bucket) bucket.jobs += 1;
    }
    return Array.from(buckets.values()).map((b) => ({ date: b.label, jobs: b.jobs }));
  }, [data]);

  const total = series.reduce((sum, d) => sum + d.jobs, 0);

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Activity</CardTitle>
        <CardDescription className="text-xs">Last 7 days</CardDescription>
        <CardAction className="text-right self-center">
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Total
          </div>
          <div className="text-lg font-semibold tabular-nums tracking-tight leading-tight">
            {total}
          </div>
        </CardAction>
      </CardHeader>
      <CardContent className="p-5">
        {isLoading ? (
          <Skeleton className="h-[240px] w-full" />
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : total === 0 ? (
          <EmptyState
            icon={BarChart3}
            title="No activity yet"
            description="Submit a video to see daily activity here."
          />
        ) : (
          <ChartContainer config={chartConfig} className="h-[240px] w-full">
            <BarChart data={series} margin={{ top: 8, right: 4, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="jobs-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-jobs)" stopOpacity={0.95} />
                  <stop offset="100%" stopColor="var(--color-jobs)" stopOpacity={0.55} />
                </linearGradient>
              </defs>
              <CartesianGrid
                vertical={false}
                strokeDasharray="3 3"
                stroke="var(--border)"
              />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tickMargin={10}
                fontSize={11}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                tickMargin={6}
                fontSize={11}
                width={28}
              />
              <ChartTooltip
                cursor={{ fill: "var(--accent-subtle)" }}
                content={<ChartTooltipContent />}
              />
              <Bar
                dataKey="jobs"
                fill="url(#jobs-fill)"
                radius={[4, 4, 0, 0]}
                animationDuration={500}
                animationEasing="ease-out"
              />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
