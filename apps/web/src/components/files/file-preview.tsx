"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { API_BASE, ApiError } from "@/lib/api-client";
import { FileMetadataPanel } from "./file-metadata-panel";
import type { FileObject } from "@video-to-insights-pipeline/shared";

interface FilePreviewProps {
  file: FileObject | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Adapted from the starter's file-preview.tsx. Two preview modes:
//   .mp4 — inline <video controls> streaming from the presigned URL.
//   .json — pretty-printed body inside a max-height scroll area; the URL
//           is short-lived but we fetch the body synchronously to render
//           it without bouncing the user to a new tab.
export function FilePreview({ file, open, onOpenChange }: FilePreviewProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [jsonBody, setJsonBody] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!file || !open) {
      setPreviewUrl(null);
      setJsonBody(null);
      setError(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        if (file.kind === "source") {
          // Video: presigned URL — <video> handles cross-origin transparently.
          const res = await fetch(
            `${API_BASE}/files/preview?key=${encodeURIComponent(file.key)}`,
          );
          if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status);
          const body = (await res.json()) as { url: string };
          if (!cancelled) setPreviewUrl(body.url);
        } else {
          // JSON: proxy through the API to avoid a cross-origin browser fetch
          // to B2 (no CORS rule on the bucket in dev).
          const jsonRes = await fetch(
            `${API_BASE}/files/content?key=${encodeURIComponent(file.key)}`,
          );
          if (!jsonRes.ok) throw new ApiError(`HTTP ${jsonRes.status}`, jsonRes.status);
          const parsed = (await jsonRes.json()) as unknown;
          if (!cancelled) setJsonBody(JSON.stringify(parsed, null, 2));
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load preview");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [file, open]);

  if (!file) return null;

  const isVideo = file.kind === "source";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="truncate font-mono text-sm">
            {file.key}
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
          <div className="rounded-lg border bg-muted/30 min-h-[200px] overflow-hidden">
            {error ? (
              <div className="text-center text-muted-foreground p-8">
                <p className="text-sm">Preview failed</p>
                <p className="text-xs mt-1">{error}</p>
              </div>
            ) : isVideo && previewUrl ? (
              <video
                controls
                playsInline
                preload="metadata"
                className="w-full max-h-[60vh] rounded"
                src={previewUrl}
              >
                Your browser does not support the video tag.
              </video>
            ) : !isVideo && jsonBody !== null ? (
              <pre className="max-h-[60vh] overflow-auto p-4 text-xs font-mono leading-relaxed">
                {jsonBody}
              </pre>
            ) : (
              <Skeleton className="h-48 w-full m-4" />
            )}
          </div>
          <FileMetadataPanel file={file} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
