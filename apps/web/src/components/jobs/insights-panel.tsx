"use client";

import { useEffect, useState } from "react";
import { artifactUrl } from "@/lib/api-client";
import type { Insight } from "@video-to-insights-pipeline/shared";

interface InsightsPanelProps {
  jobId: string;
  onSeek: (seconds: number) => void;
}

function fmtTime(s: number): string {
  const total = Math.max(0, Math.floor(s));
  const m = Math.floor(total / 60);
  const sec = total % 60;
  return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
}

/**
 * Fetches insights.json (via the API's 302 redirect) and renders one
 * clickable row per section. Clicking a row calls `onSeek(start_seconds)`
 * which the parent wires to the video element's `currentTime` setter.
 */
export function InsightsPanel({ jobId, onSeek }: InsightsPanelProps) {
  const [insights, setInsights] = useState<Insight[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // `redirect: "follow"` is the browser default — the API 302s and
        // we land on the presigned B2 URL transparently.
        const res = await fetch(artifactUrl(jobId, "insights"));
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = (await res.json()) as { insights: Insight[] };
        if (!cancelled) setInsights(body.insights ?? []);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (error) {
    return <div className="text-sm text-muted-foreground">Couldn&apos;t load insights: {error}</div>;
  }
  if (insights === null) {
    return <div className="text-sm text-muted-foreground">Loading insights…</div>;
  }
  if (insights.length === 0) {
    return <div className="text-sm text-muted-foreground">No insights returned.</div>;
  }

  return (
    <ul className="space-y-2">
      {insights.map((ins) => (
        <li key={ins.index}>
          <button
            type="button"
            className="w-full text-left rounded-md border bg-card px-3 py-2 hover:bg-accent transition-colors"
            onClick={() => onSeek(ins.start_seconds)}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium text-sm">{ins.title}</span>
              <span className="font-mono text-xs text-muted-foreground">
                {fmtTime(ins.start_seconds)}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{ins.summary}</p>
          </button>
        </li>
      ))}
    </ul>
  );
}
