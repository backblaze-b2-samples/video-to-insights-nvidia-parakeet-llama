"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { humanizeBytes, formatDate } from "@/lib/utils";
import type { FileObject } from "@video-to-insights-pipeline/shared";

interface FileMetadataPanelProps {
  file: FileObject;
}

function MetaRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between text-sm gap-3">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="font-mono text-right max-w-[70%] truncate">{value}</span>
    </div>
  );
}

// Try to extract the {video_id} segment from a pipeline key. Returns
// undefined for the jobs-index sentinel at the prefix root.
function extractVideoId(key: string): string | undefined {
  const parts = key.split("/");
  if (parts.length < 3) return undefined;
  return parts[1];
}

// Adapted from the starter's file-metadata-panel.tsx. Shows the four
// generic fields plus the parsed video_id when present.
export function FileMetadataPanel({ file }: FileMetadataPanelProps) {
  const videoId = extractVideoId(file.key);
  return (
    <Card>
      <CardHeader className="pb-3 px-5 pt-5">
        <CardTitle className="card-title">File details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 px-5 pb-5">
        <MetaRow label="Kind" value={file.kind} />
        <MetaRow label="Size" value={humanizeBytes(file.size)} />
        <MetaRow
          label="Last modified"
          value={file.last_modified ? formatDate(file.last_modified) : "—"}
        />
        {videoId ? <MetaRow label="Video ID" value={videoId} /> : null}
        <Separator />
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Key
        </p>
        <div className="font-mono text-xs text-foreground break-all">
          {file.key}
        </div>
      </CardContent>
    </Card>
  );
}
