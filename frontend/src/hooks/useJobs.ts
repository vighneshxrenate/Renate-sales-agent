"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ScrapeJob, ScrapeJobListResponse } from "@/lib/types";

export function useJobs(params: { page?: number; status?: string } = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => apiFetch<ScrapeJobListResponse>(`/jobs?${searchParams}`),
  });
}

export function useJob(id: string) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => apiFetch<ScrapeJob>(`/jobs/${id}`),
    refetchInterval: (query) => {
      const job = query.state.data;
      return job && (job.status === "running" || job.status === "pending")
        ? 5000
        : false;
    },
  });
}

export function useTriggerJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      source: string;
      keywords: string;
      location_filter?: string;
      max_pages?: number;
    }) =>
      apiFetch<ScrapeJob>("/jobs", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
