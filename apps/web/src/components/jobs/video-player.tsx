"use client";

import { forwardRef } from "react";
import { artifactUrl } from "@/lib/api-client";

interface VideoPlayerProps {
  jobId: string;
}

/**
 * Native <video> element. The `src` points at the API redirect endpoint
 * (`/jobs/{id}/source`) which 302s to a presigned B2 URL — the browser
 * follows the redirect transparently and streams via HTTP Range requests.
 *
 * forwardRef so the parent page can call `videoRef.current.currentTime = ...`
 * when an insight card is clicked.
 */
export const VideoPlayer = forwardRef<HTMLVideoElement, VideoPlayerProps>(
  function VideoPlayer({ jobId }, ref) {
    return (
      <video
        ref={ref}
        controls
        playsInline
        preload="metadata"
        className="w-full rounded-lg border bg-black aspect-video"
        src={artifactUrl(jobId, "source")}
      >
        Your browser does not support the video tag.
      </video>
    );
  }
);
