"use client";

import { use } from "react";
import Link from "next/link";
import { useJob } from "@/hooks/useJobs";
import { formatDateTime } from "@/lib/utils";

export default function JobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: job, isLoading } = useJob(id);

  if (isLoading) return <p className="text-[var(--muted-foreground)]">Loading...</p>;
  if (!job) return <p>Job not found</p>;

  const progress =
    job.total_pages && job.total_pages > 0
      ? Math.round((job.pages_scraped / job.total_pages) * 100)
      : 0;

  return (
    <div>
      <Link
        href="/jobs"
        className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] mb-4 inline-block"
      >
        &larr; Back to Jobs
      </Link>

      <h2 className="text-2xl font-bold mb-6 capitalize">
        {job.source} Scrape Job
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Status</p>
          <p className="text-xl font-bold capitalize mt-1">{job.status}</p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Progress</p>
          <p className="text-xl font-bold mt-1">
            {job.pages_scraped} / {job.total_pages ?? "?"} pages
          </p>
          <div className="mt-2 bg-[var(--muted)] rounded-full h-2">
            <div
              className="bg-[var(--primary)] rounded-full h-2 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Leads Found</p>
          <p className="text-xl font-bold mt-1">{job.leads_found}</p>
          <p className="text-xs text-[var(--muted-foreground)]">
            {job.leads_new} new after dedup
          </p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Triggered By</p>
          <p className="text-xl font-bold capitalize mt-1">{job.triggered_by}</p>
        </div>
      </div>

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
        <h3 className="font-semibold mb-3">Details</h3>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <dt className="text-[var(--muted-foreground)]">Keywords</dt>
          <dd>{job.keywords || "—"}</dd>
          <dt className="text-[var(--muted-foreground)]">Location Filter</dt>
          <dd>{job.location_filter || "—"}</dd>
          <dt className="text-[var(--muted-foreground)]">Started</dt>
          <dd>{job.started_at ? formatDateTime(job.started_at) : "—"}</dd>
          <dt className="text-[var(--muted-foreground)]">Completed</dt>
          <dd>{job.completed_at ? formatDateTime(job.completed_at) : "—"}</dd>
          {job.error_message && (
            <>
              <dt className="text-[var(--destructive)]">Error</dt>
              <dd className="text-[var(--destructive)]">{job.error_message}</dd>
            </>
          )}
        </dl>
      </div>
    </div>
  );
}
