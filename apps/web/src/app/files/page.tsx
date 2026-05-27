import Link from "next/link";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { FileBrowser } from "@/components/files/file-browser";

export default function FilesPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Files</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            All objects stored in B2 under the{" "}
            <code className="font-mono text-xs">video-to-insights-pipeline/</code>{" "}
            prefix.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/new">
            <Plus className="h-3.5 w-3.5" />
            New job
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <FileBrowser />
      </div>
    </div>
  );
}
