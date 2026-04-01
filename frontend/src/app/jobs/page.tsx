"use client";

import { useState } from "react";
import Link from "next/link";
import { useJobs, useTriggerJob } from "@/hooks/useJobs";
import { formatDateTime } from "@/lib/utils";

const SOURCES = [
  { value: "linkedin", label: "LinkedIn" },
  { value: "naukri", label: "Naukri" },
  { value: "indeed", label: "Indeed" },
  { value: "google_jobs", label: "Google Jobs" },
  { value: "career_page", label: "Career Pages" },
];

export default function JobsPage() {
  const [showDialog, setShowDialog] = useState(false);
  const [formSource, setFormSource] = useState("linkedin");
  const [formKeywords, setFormKeywords] = useState("");
  const [formLocation, setFormLocation] = useState("");

  const { data, isLoading } = useJobs({ page: 1 });
  const triggerJob = useTriggerJob();

  const handleSubmit = () => {
    if (!formKeywords.trim()) return;
    triggerJob.mutate(
      {
        source: formSource,
        keywords: formKeywords,
        location_filter: formLocation || undefined,
      },
      { onSuccess: () => setShowDialog(false) }
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Scrape Jobs</h2>
        <button
          onClick={() => setShowDialog(true)}
          className="px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm hover:opacity-90"
        >
          New Scrape Job
        </button>
      </div>

      {showDialog && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Trigger Scrape Job</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-[var(--muted-foreground)] block mb-1">
                  Source
                </label>
                <select
                  value={formSource}
                  onChange={(e) => setFormSource(e.target.value)}
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
                  value={formKeywords}
                  onChange={(e) => setFormKeywords(e.target.value)}
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
                  value={formLocation}
                  onChange={(e) => setFormLocation(e.target.value)}
                  className="w-full bg-[var(--muted)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6 justify-end">
              <button
                onClick={() => setShowDialog(false)}
                className="px-4 py-2 border border-[var(--border)] rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!formKeywords.trim() || triggerJob.isPending}
                className="px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm hover:opacity-90 disabled:opacity-40"
              >
                {triggerJob.isPending ? "Starting..." : "Start Scraping"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Keywords</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Progress</th>
              <th className="px-4 py-3">Leads</th>
              <th className="px-4 py-3">Started</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                  Loading...
                </td>
              </tr>
            ) : data?.jobs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                  No jobs yet. Click &ldquo;New Scrape Job&rdquo; to start.
                </td>
              </tr>
            ) : (
              data?.jobs.map((job) => (
                <tr
                  key={job.id}
                  className="border-b border-[var(--border)] hover:bg-[var(--muted)] transition-colors"
                >
                  <td className="px-4 py-3 capitalize">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-[var(--primary)] hover:underline"
                    >
                      {job.source}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{job.keywords || "—"}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        job.status === "running"
                          ? "bg-blue-500/20 text-blue-400"
                          : job.status === "completed"
                            ? "bg-green-500/20 text-green-400"
                            : job.status === "failed"
                              ? "bg-red-500/20 text-red-400"
                              : "bg-[var(--muted)] text-[var(--muted-foreground)]"
                      }`}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {job.pages_scraped}/{job.total_pages ?? "?"}
                  </td>
                  <td className="px-4 py-3">
                    {job.leads_new} new / {job.leads_found} total
                  </td>
                  <td className="px-4 py-3 text-[var(--muted-foreground)]">
                    {job.started_at ? formatDateTime(job.started_at) : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
