"use client";

import { useState } from "react";
import Link from "next/link";
import { useJobs } from "@/hooks/useJobs";
import { formatDateTime } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card } from "@/components/ui/Card";
import { TriggerJobDialog } from "@/components/jobs/TriggerJobDialog";

export default function JobsPage() {
  const [showDialog, setShowDialog] = useState(false);
  const { data, isLoading } = useJobs({ page: 1 });

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

      <TriggerJobDialog
        open={showDialog}
        onClose={() => setShowDialog(false)}
      />

      <Card className="overflow-hidden">
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
                      {job.source.replace("_", " ")}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{job.keywords || "—"}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={job.status} variant="job" />
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
      </Card>
    </div>
  );
}
