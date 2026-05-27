"use client";

import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SubmitForm } from "@/components/jobs/submit-form";

// Mirrors the layout of the starter's /upload page — page header +
// single Card hosting the input form. On submit we route to the job
// detail page where the user watches polling progress and playback.
export default function NewJobPage() {
  const router = useRouter();

  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">New job</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Paste a YouTube URL. The source video lands in Backblaze B2 and
          NVIDIA NIM extracts timestamped insights you can click to seek.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2 max-w-2xl">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Submit a video</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <SubmitForm onSubmitted={(jobId) => router.push(`/jobs/${jobId}`)} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
