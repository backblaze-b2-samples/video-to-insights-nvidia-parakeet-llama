"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSubmitJob } from "@/lib/queries";

interface SubmitFormProps {
  onSubmitted: (jobId: string) => void;
}

// Minimal submit form — URL field + Run button + transient submitting
// hint. Mirrors the starter's UploadForm card-content rhythm (space-y-4
// fields, button row at the bottom).
export function SubmitForm({ onSubmitted }: SubmitFormProps) {
  const [url, setUrl] = useState("");
  const submit = useSubmitJob();

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    const trimmed = url.trim();
    const res = await submit.mutateAsync({ youtube_url: trimmed });
    setUrl("");
    onSubmitted(res.job_id);
  };

  return (
    <form onSubmit={handle} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="url">Video URL (YouTube)</Label>
        <Input
          id="url"
          type="url"
          inputMode="url"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          disabled={submit.isPending}
        />
        <p className="text-xs text-muted-foreground">
          YouTube only for now. The video lands in B2 before any analysis runs.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={submit.isPending || !url.trim()}>
          {submit.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Run
        </Button>
        {submit.isPending ? (
          <span className="text-xs text-muted-foreground">Submitting…</span>
        ) : submit.error ? (
          <span className="text-sm text-destructive">{submit.error.message}</span>
        ) : null}
      </div>
    </form>
  );
}
