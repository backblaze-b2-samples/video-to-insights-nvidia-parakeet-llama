import type { FileObject } from "@video-to-insights-pipeline/shared";

export interface TreeFolder {
  type: "folder";
  name: string;
  path: string;
  children: TreeNode[];
}

export interface TreeFile {
  type: "file";
  name: string;
  data: FileObject;
}

export type TreeNode = TreeFolder | TreeFile;

// Pipeline keys look like:
//   video-to-insights-pipeline/<video_id>/<kind>.<ext>
//   video-to-insights-pipeline/jobs-index.json   (root sentinel — skipped)
// Returns one folder per video_id with its 1-4 artifacts as leaves.
const VIDEO_ID_KEY = /^[^/]+\/([^/]+)\/[^/]+$/;

function leafName(file: FileObject): string {
  const parts = file.key.split("/");
  return parts[parts.length - 1] || file.key;
}

export function buildFileTree(files: FileObject[]): TreeNode[] {
  const folders = new Map<string, TreeFolder>();
  const orphans: TreeFile[] = [];

  for (const file of files) {
    // jobs-index.json sits at the prefix root — exclude it from the
    // tree to keep the UI focused on per-video artifacts.
    if (file.kind === "jobs_index") continue;
    const match = VIDEO_ID_KEY.exec(file.key);
    if (!match) {
      orphans.push({ type: "file", name: leafName(file), data: file });
      continue;
    }
    const videoId = match[1];
    let folder = folders.get(videoId);
    if (!folder) {
      folder = {
        type: "folder",
        name: videoId,
        path: videoId,
        children: [],
      };
      folders.set(videoId, folder);
    }
    folder.children.push({ type: "file", name: leafName(file), data: file });
  }

  // Within each folder, order by kind so source.mp4 is always first.
  const KIND_ORDER: Record<string, number> = {
    source: 0,
    transcript: 1,
    insights: 2,
    manifest: 3,
  };
  for (const folder of folders.values()) {
    folder.children.sort((a, b) => {
      if (a.type !== "file" || b.type !== "file") return 0;
      return (
        (KIND_ORDER[a.data.kind] ?? 99) - (KIND_ORDER[b.data.kind] ?? 99)
      );
    });
  }

  // Folders first, newest-first by their newest child's last_modified.
  const folderList = Array.from(folders.values()).sort((a, b) => {
    const aTs = newestTimestamp(a);
    const bTs = newestTimestamp(b);
    return bTs - aTs;
  });

  return [...folderList, ...orphans];
}

function newestTimestamp(folder: TreeFolder): number {
  let max = 0;
  for (const child of folder.children) {
    if (child.type !== "file") continue;
    const ts = child.data.last_modified
      ? new Date(child.data.last_modified).getTime()
      : 0;
    if (ts > max) max = ts;
  }
  return max;
}
