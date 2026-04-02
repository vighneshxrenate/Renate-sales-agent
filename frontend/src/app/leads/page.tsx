"use client";

import { useState } from "react";
import { useLeads } from "@/hooks/useLeads";
import { LeadFilters } from "@/components/leads/LeadFilters";
import { LeadsTable } from "@/components/leads/LeadsTable";

export default function LeadsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");

  const { data, isLoading } = useLeads({
    page,
    per_page: 50,
    search: search || undefined,
    source: source || undefined,
    status: status || undefined,
  });

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Leads</h2>
        <a
          href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/leads/export?${new URLSearchParams(
            Object.fromEntries(
              Object.entries({ source, status }).filter(([, v]) => v)
            )
          )}`}
          className="px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm hover:opacity-90"
        >
          Export CSV
        </a>
      </div>

      <LeadFilters
        search={search}
        source={source}
        status={status}
        onSearchChange={(v) => { setSearch(v); setPage(1); }}
        onSourceChange={(v) => { setSource(v); setPage(1); }}
        onStatusChange={(v) => { setStatus(v); setPage(1); }}
      />

      <LeadsTable leads={data?.leads} isLoading={isLoading} />

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm">
          <span className="text-[var(--muted-foreground)]">
            {data?.total} leads total
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 rounded border border-[var(--border)] disabled:opacity-40"
            >
              Prev
            </button>
            <span className="px-3 py-1">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1 rounded border border-[var(--border)] disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
