"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { LeadListResponse, Lead, LeadStats } from "@/lib/types";

export function useLeads(params: {
  page?: number;
  per_page?: number;
  search?: string;
  source?: string;
  status?: string;
  location?: string;
}) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  return useQuery({
    queryKey: ["leads", params],
    queryFn: () => apiFetch<LeadListResponse>(`/leads?${searchParams}`),
  });
}

export function useLead(id: string) {
  return useQuery({
    queryKey: ["lead", id],
    queryFn: () => apiFetch<Lead>(`/leads/${id}`),
  });
}

export function useLeadStats() {
  return useQuery({
    queryKey: ["lead-stats"],
    queryFn: () => apiFetch<LeadStats>("/leads/stats"),
  });
}

export function useUpdateLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: { status?: string; company_name?: string; location?: string };
    }) =>
      apiFetch<Lead>(`/leads/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["lead", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["lead-stats"] });
    },
  });
}
