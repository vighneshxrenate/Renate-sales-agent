"use client";

import { use } from "react";
import Link from "next/link";
import { useJob, useCancelJob } from "@/hooks/useJobs";
import { formatDateTime } from "@/lib/utils";
import { Card, StatCard } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function JobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: job, isLoading } = useJob(id);
  const cancelJob = useCancelJob();

  if (isLoading)
    return <p className="text-[var(--muted-foreground)]">Loading...</p>;
  if (!job) return <p>Job not found</p>;

  const progress =
    job.total_pages && job.total_pages > 0
      ? Math.round((job.pages_scraped / job.total_pages) * 100)
      : 0;

  const canCancel = job.status === "pending" || job.status === "running";

  return (
    <div>
      <Link
        href="/jobs"
        className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] mb-4 inline-block"
      >
        &larr; Back to Jobs
      </Link>

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold capitalize">
          {job.source.replace("_", " ")} Scrape Job
        </h2>
        {canCancel && (
          <button
            onClick={() => cancelJob.mutate(job.id)}
            disabled={cancelJob.isPending}
            className="px-4 py-2 border border-[var(--destructive)] text-[var(--destructive)] rounded-lg text-sm hover:bg-[var(--destructive)] hover:text-white transition-colors disabled:opacity-40"
          >
            {cancelJob.isPending ? "Cancelling..." : "Cancel Job"}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card className="p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Status</p>
          <div className="mt-2">
            <StatusBadge status={job.status} variant="job" />
          </div>
        </Card>
        <Card className="p-4">
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
        </Card>
        <Card className="p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Leads Found</p>
          <p className="text-xl font-bold mt-1">{job.leads_found}</p>
          <p className="text-xs text-[var(--muted-foreground)]">
            {job.leads_new} new after dedup
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Triggered By</p>
          <p className="text-xl font-bold capitalize mt-1">
            {job.triggered_by}
          </p>
        </Card>
      </div>

      <Card className="p-5">
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
              <dd className="text-[var(--destructive)]">
                {job.error_message}
              </dd>
            </>
          )}
        </dl>
      </Card>
    </div>
  );
}
