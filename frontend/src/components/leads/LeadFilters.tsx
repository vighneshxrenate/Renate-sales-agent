"use client";

import { SOURCES, STATUSES } from "@/lib/constants";

export function LeadFilters({
  search,
  source,
  status,
  onSearchChange,
  onSourceChange,
  onStatusChange,
}: {
  search: string;
  source: string;
  status: string;
  onSearchChange: (v: string) => void;
  onSourceChange: (v: string) => void;
  onStatusChange: (v: string) => void;
}) {
  return (
    <div className="flex gap-3 mb-4">
      <input
        type="text"
        placeholder="Search companies..."
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        className="flex-1 bg-[var(--muted)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
      />
      <select
        value={source}
        onChange={(e) => onSourceChange(e.target.value)}
        className="bg-[var(--muted)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
      >
        <option value="">All Sources</option>
        {SOURCES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
      <select
        value={status}
        onChange={(e) => onStatusChange(e.target.value)}
        className="bg-[var(--muted)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
      >
        <option value="">All Statuses</option>
        {STATUSES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
    </div>
  );
}
