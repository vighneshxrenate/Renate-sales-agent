"use client";

import { useLeadStats } from "@/hooks/useLeads";
import { useJobs } from "@/hooks/useJobs";

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
      <p className="text-sm text-[var(--muted-foreground)]">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && (
        <p className="text-xs text-[var(--muted-foreground)] mt-1">{sub}</p>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useLeadStats();
  const { data: jobsData } = useJobs({ page: 1 });

  const runningJobs =
    jobsData?.jobs.filter((j) => j.status === "running").length ?? 0;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total Leads"
          value={statsLoading ? "..." : (stats?.total ?? 0)}
        />
        <StatCard
          label="Active Jobs"
          value={runningJobs}
          sub="currently scraping"
        />
        <StatCard
          label="Sources"
          value={statsLoading ? "..." : Object.keys(stats?.by_source ?? {}).length}
        />
        <StatCard
          label="New Leads"
          value={statsLoading ? "..." : (stats?.by_status?.new ?? 0)}
          sub="awaiting review"
        />
      </div>

      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
            <h3 className="font-semibold mb-4">Leads by Source</h3>
            {Object.entries(stats.by_source).length === 0 ? (
              <p className="text-[var(--muted-foreground)] text-sm">
                No leads yet. Trigger a scrape job to get started.
              </p>
            ) : (
              <div className="space-y-3">
                {Object.entries(stats.by_source).map(([source, count]) => (
                  <div key={source} className="flex items-center justify-between">
                    <span className="text-sm capitalize">{source}</span>
                    <span className="text-sm font-mono">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
            <h3 className="font-semibold mb-4">Leads by Status</h3>
            {Object.entries(stats.by_status).length === 0 ? (
              <p className="text-[var(--muted-foreground)] text-sm">
                No leads yet.
              </p>
            ) : (
              <div className="space-y-3">
                {Object.entries(stats.by_status).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <span className="text-sm capitalize">{status}</span>
                    <span className="text-sm font-mono">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
