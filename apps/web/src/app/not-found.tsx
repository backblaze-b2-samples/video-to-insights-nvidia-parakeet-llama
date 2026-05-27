import Link from "next/link";
import { FileQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="flex items-center justify-center w-16 h-16 rounded-full bg-muted border border-border mb-6">
        <FileQuestion className="h-8 w-8 text-muted-foreground" />
      </div>
      <h1 className="text-2xl font-semibold tracking-tight">
        Page not found
      </h1>
      <p className="text-sm text-muted-foreground mt-2 max-w-md">
        That URL doesn&apos;t match any route in this app.
      </p>
      <div className="mt-6">
        <Button asChild size="sm">
          <Link href="/">Back to home</Link>
        </Button>
      </div>
    </div>
  );
}
