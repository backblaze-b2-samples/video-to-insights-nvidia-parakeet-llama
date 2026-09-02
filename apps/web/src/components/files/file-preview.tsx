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
  const [preview, setPreview] = useState<{
    error: string | null;
    jsonBody: string | null;
    key: string;
    previewUrl: string | null;
  } | null>(null);

  useEffect(() => {
    if (!file || !open) return;
    const activeKey = file.key;
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
          if (!cancelled) {
            setPreview({
              error: null,
              jsonBody: null,
              key: activeKey,
              previewUrl: body.url,
            });
          }
        } else {
          // JSON: proxy through the API to avoid a cross-origin browser fetch
          // to B2 (no CORS rule on the bucket in dev).
          const jsonRes = await fetch(
            `${API_BASE}/files/content?key=${encodeURIComponent(file.key)}`,
          );
          if (!jsonRes.ok) throw new ApiError(`HTTP ${jsonRes.status}`, jsonRes.status);
          const parsed = (await jsonRes.json()) as unknown;
          if (!cancelled) {
            setPreview({
              error: null,
              jsonBody: JSON.stringify(parsed, null, 2),
              key: activeKey,
              previewUrl: null,
            });
          }
        }
      } catch (e) {
        if (!cancelled) {
          setPreview({
            error: e instanceof Error ? e.message : "Failed to load preview",
            jsonBody: null,
            key: activeKey,
            previewUrl: null,
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [file, open]);

  if (!file) return null;

  const isVideo = file.kind === "source";
  const activePreview = open && preview?.key === file.key ? preview : null;

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
            {activePreview?.error ? (
              <div className="text-center text-muted-foreground p-8">
                <p className="text-sm">Preview failed</p>
                <p className="text-xs mt-1">{activePreview.error}</p>
              </div>
            ) : isVideo && activePreview?.previewUrl ? (
              <video
                controls
                playsInline
                preload="metadata"
                className="w-full max-h-[60vh] rounded"
                src={activePreview.previewUrl}
              >
                Your browser does not support the video tag.
              </video>
            ) : !isVideo && activePreview?.jsonBody !== null && activePreview?.jsonBody !== undefined ? (
              <pre className="max-h-[60vh] overflow-auto p-4 text-xs font-mono leading-relaxed">
                {activePreview.jsonBody}
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
