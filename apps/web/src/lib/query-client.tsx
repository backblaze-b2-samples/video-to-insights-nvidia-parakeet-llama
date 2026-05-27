"use client";

import {
  QueryClient,
  QueryClientProvider as TanstackProvider,
} from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "@/lib/api-client";

// Defaults sized for the jobs-poll pattern:
//  - 30s staleTime — terminal job states don't change; for in-flight jobs the
//    per-query `refetchInterval` in `useJob` drives updates, so a generous
//    staleTime just suppresses redundant background refetches.
//  - retry: 1, but never retry 4xx — those won't get better on a second try.
//  - refetchOnWindowFocus stays on (TanStack default) so a job that finished
//    while the tab was inactive surfaces as soon as the user comes back.
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            return false;
          }
          return failureCount < 1;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function QueryClientProvider({ children }: { children: React.ReactNode }) {
  // Lazy single-instance per browser session — avoids re-creating the
  // client on every render.
  const [client] = useState(makeQueryClient);
  return <TanstackProvider client={client}>{children}</TanstackProvider>;
}
