"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { DailyReport, ReportListResponse } from "@/lib/types";

export function useReports(params: { page?: number } = {}) {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));

  return useQuery({
    queryKey: ["reports", params],
    queryFn: () => apiFetch<ReportListResponse>(`/reports?${searchParams}`),
  });
}

export function useReport(id: string) {
  return useQuery({
    queryKey: ["report", id],
    queryFn: () => apiFetch<DailyReport>(`/reports/${id}`),
  });
}
