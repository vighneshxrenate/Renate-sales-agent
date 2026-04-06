"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { SOURCES } from "@/lib/constants";
import { useTriggerJob } from "@/hooks/useJobs";

export function TriggerJobDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [source, setSource] = useState("linkedin");
  const [keywords, setKeywords] = useState("");
  const [location, setLocation] = useState("");
  const triggerJob = useTriggerJob();

  const handleSubmit = () => {
    if (!keywords.trim()) return;
    triggerJob.mutate(
      {
        source,
        keywords,
        location_filter: location || undefined,
      },
      {
        onSuccess: () => {
          onClose();
          setKeywords("");
          setLocation("");
        },
      }
    );
  };

  return (
    <Dialog open={open} onClose={onClose} title="Trigger Scrape Job">
      <div className="space-y-3">
        <div>
          <label className="text-sm text-[var(--muted-foreground)] block mb-1">
            Source
          </label>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="w-full bg-[var(--muted)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          >
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-sm text-[var(--muted-foreground)] block mb-1">
            Keywords
          </label>
          <input
            type="text"
            placeholder="e.g. software engineer, data scientist"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            className="w-full bg-[var(--muted)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-sm text-[var(--muted-foreground)] block mb-1">
            Location (optional)
          </label>
          <input
            type="text"
            placeholder="e.g. Bangalore, Mumbai"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="w-full bg-[var(--muted)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          />
        </div>
      </div>
      <div className="flex gap-3 mt-6 justify-end">
        <button
          onClick={onClose}
          className="px-4 py-2 border border-[var(--border)] rounded-lg text-sm"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={!keywords.trim() || triggerJob.isPending}
          className="px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm hover:opacity-90 disabled:opacity-40"
        >
          {triggerJob.isPending ? "Starting..." : "Start Scraping"}
        </button>
      </div>
    </Dialog>
  );
}
