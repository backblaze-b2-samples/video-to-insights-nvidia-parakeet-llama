import Link from "next/link";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { ActivityChart } from "@/components/dashboard/activity-chart";
import { RecentVideosTable } from "@/components/dashboard/recent-videos-table";
import { LastProcessedCard } from "@/components/dashboard/last-processed-card";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Paste a YouTube URL, get a transcript + seekable insights stored in
            Backblaze B2.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/new">
            <Plus className="h-3.5 w-3.5" />
            New job
          </Link>
        </Button>
      </div>
      <StatsCards />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 animate-fade-in-up stagger-2">
          <ActivityChart />
        </div>
        <div className="animate-fade-in-up stagger-3">
          <LastProcessedCard />
        </div>
      </div>
      <div className="animate-fade-in-up stagger-4">
        <RecentVideosTable />
      </div>
    </div>
  );
}
