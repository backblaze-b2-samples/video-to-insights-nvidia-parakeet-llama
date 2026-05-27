"use client";

import { AlertTriangle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/api-client";

interface HealthResponse {
  status: "healthy" | "degraded";
  b2_connected: boolean;
  nvidia_configured: boolean;
}

async function fetchHealth(): Promise<HealthResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      signal: AbortSignal.timeout(5_000),
    });
    if (!res.ok) return null;
    return (await res.json()) as HealthResponse;
  } catch {
    return null;
  }
}

/**
 * Shows a top-of-app warning when the API can't reach B2. NVIDIA is
 * intentionally NOT surfaced here — it's optional and graceful
 * degradation is the whole point. The page renders a per-job notice
 * for "no analysis" cases instead.
 */
export function HealthBanner() {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: false,
  });

  if (!data || data.b2_connected) return null;

  return (
    <div
      role="alert"
      className="flex items-center gap-2 border-b border-[color-mix(in_oklab,var(--attention)_30%,var(--border))] bg-[var(--attention-subtle)] px-4 py-2 text-xs text-[var(--attention)]"
    >
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      <span className="font-medium">B2 not connected.</span>
      <span className="text-foreground/70">
        The API is running but can&apos;t reach Backblaze. Check your{" "}
        <code className="font-mono text-[11px]">.env</code> credentials and
        bucket region, then restart the API.
      </span>
    </div>
  );
}
