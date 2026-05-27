"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Copy,
  Eye,
  ExternalLink,
  MoreHorizontal,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileIcon,
  FileTextIcon,
  FileVideoIcon,
  ListIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { FilePreview } from "./file-preview";
import { ApiError, API_BASE } from "@/lib/api-client";
import { useFiles } from "@/lib/queries";
import { humanizeBytes, formatDate } from "@/lib/utils";
import { buildFileTree, type TreeNode, type TreeFolder } from "@/lib/file-tree";
import type { FileKind, FileObject } from "@video-to-insights-pipeline/shared";

// Stable component (declared at module scope so React Compiler treats it
// as a normal element). Maps our 5 artifact kinds to lucide icons.
function FileTypeIcon({
  kind,
  className,
}: {
  kind: FileKind;
  className?: string;
}) {
  if (kind === "source") return <FileVideoIcon className={className} />;
  if (kind === "transcript" || kind === "insights" || kind === "manifest")
    return <FileTextIcon className={className} />;
  if (kind === "jobs_index") return <ListIcon className={className} />;
  return <FileIcon className={className} />;
}

const KIND_LABELS: Record<FileKind, string> = {
  source: "Source video",
  transcript: "Transcript",
  insights: "Insights",
  manifest: "Manifest",
  jobs_index: "Jobs index",
  other: "Other",
};

function countFiles(node: TreeFolder): number {
  let count = 0;
  for (const child of node.children) {
    if (child.type === "file") count += 1;
    else count += countFiles(child);
  }
  return count;
}

interface TreeRowProps {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onPreview: (file: FileObject) => void;
  onOpen: (file: FileObject) => void;
  onCopyKey: (file: FileObject) => void;
}

function TreeRow({
  node,
  depth,
  expanded,
  onToggle,
  onPreview,
  onOpen,
  onCopyKey,
}: TreeRowProps) {
  if (node.type === "folder") {
    const isOpen = expanded.has(node.path);
    const fileCount = countFiles(node);
    return (
      <>
        <button
          onClick={() => onToggle(node.path)}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-sm hover:bg-accent/60 tree-row transition-colors group"
          style={{ paddingLeft: `${depth * 20 + 12}px` }}
        >
          {isOpen ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          {isOpen ? (
            <FolderOpen className="h-4 w-4 shrink-0 text-[var(--attention)]" />
          ) : (
            <Folder className="h-4 w-4 shrink-0 text-[var(--attention)]" />
          )}
          <span className="font-medium truncate font-mono text-xs">{node.name}</span>
          <span className="ml-auto text-xs text-muted-foreground shrink-0">
            {fileCount} {fileCount === 1 ? "file" : "files"}
          </span>
        </button>
        {isOpen &&
          node.children.map((child) => (
            <TreeRow
              key={child.type === "folder" ? child.path : child.data.key}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              onPreview={onPreview}
              onOpen={onOpen}
              onCopyKey={onCopyKey}
            />
          ))}
      </>
    );
  }

  const file = node.data;
  return (
    <div
      className="group flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-sm hover:bg-accent/60 tree-row transition-colors"
      style={{ paddingLeft: `${depth * 20 + 32}px` }}
    >
      <FileTypeIcon
        kind={file.kind}
        className="h-4 w-4 shrink-0 text-muted-foreground"
      />
      <span className="truncate">{node.name}</span>
      <span className="ml-auto flex items-center gap-4 shrink-0">
        <span className="text-xs text-muted-foreground hidden sm:inline">
          {KIND_LABELS[file.kind]}
        </span>
        <span className="font-mono text-xs text-muted-foreground tabular-nums hidden sm:inline">
          {humanizeBytes(file.size)}
        </span>
        <span className="text-xs text-muted-foreground hidden md:inline">
          {file.last_modified ? formatDate(file.last_modified) : "—"}
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <MoreHorizontal className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onPreview(file)}>
              <Eye className="mr-2 h-4 w-4" />
              Preview
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onOpen(file)}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Open in new tab
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onCopyKey(file)}>
              <Copy className="mr-2 h-4 w-4" />
              Copy key
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </span>
    </div>
  );
}

export function FileBrowser() {
  const { data, isLoading, isFetching, error, refetch } = useFiles();
  const files = useMemo(() => data?.objects ?? [], [data]);

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [previewFile, setPreviewFile] = useState<FileObject | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const tree = useMemo(() => buildFileTree(files), [files]);

  // Auto-expand on first arrival; preserve user's manual toggles after.
  useEffect(() => {
    if (files.length === 0) return;
    setExpanded((prev) => {
      if (prev.size > 0) return prev;
      const topFolders = tree
        .filter((n): n is TreeFolder => n.type === "folder")
        .map((f) => f.path);
      return new Set(topFolders);
    });
  }, [files.length, tree]);

  const toggleFolder = useCallback((path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const handleOpenInTab = async (file: FileObject) => {
    try {
      const res = await fetch(
        `${API_BASE}/files/preview?key=${encodeURIComponent(file.key)}`,
      );
      if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status);
      const body = (await res.json()) as { url: string };
      window.open(body.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Failed to open file";
      toast.error(detail);
    }
  };

  const handleCopyKey = async (file: FileObject) => {
    try {
      await navigator.clipboard.writeText(file.key);
      toast.success("Key copied to clipboard");
    } catch {
      toast.error("Couldn't copy key");
    }
  };

  const handlePreview = (file: FileObject) => {
    setPreviewFile(file);
    setPreviewOpen(true);
  };

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between border-b border-border py-4 px-5 space-y-0">
          <CardTitle className="card-title">Pipeline artifacts</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="h-7 text-xs"
            disabled={isFetching}
          >
            <RefreshCw
              className={`h-3.5 w-3.5 mr-1 ${isFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="p-3">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState error={error} onRetry={() => refetch()} />
          ) : tree.length === 0 ? (
            <EmptyState
              icon={FolderOpen}
              title="No artifacts yet"
              description="Submit a video on the dashboard to see source.mp4 and analysis JSON land here."
            />
          ) : (
            <div className="space-y-0.5">
              {tree.map((node) => (
                <TreeRow
                  key={node.type === "folder" ? node.path : node.data.key}
                  node={node}
                  depth={0}
                  expanded={expanded}
                  onToggle={toggleFolder}
                  onPreview={handlePreview}
                  onOpen={handleOpenInTab}
                  onCopyKey={handleCopyKey}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <FilePreview
        file={previewFile}
        open={previewOpen}
        onOpenChange={setPreviewOpen}
      />
    </>
  );
}
