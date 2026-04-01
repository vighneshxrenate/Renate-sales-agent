"use client";

import { use } from "react";
import Link from "next/link";
import { useReport } from "@/hooks/useReports";
import { formatDate } from "@/lib/utils";

export default function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: report, isLoading } = useReport(id);

  if (isLoading) return <p className="text-[var(--muted-foreground)]">Loading...</p>;
  if (!report) return <p>Report not found</p>;

  return (
    <div>
      <Link
        href="/reports"
        className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] mb-4 inline-block"
      >
        &larr; Back to Reports
      </Link>

      <h2 className="text-2xl font-bold mb-6">
        Report — {formatDate(report.report_date)}
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-sm text-[var(--muted-foreground)]">New Leads</p>
          <p className="text-3xl font-bold mt-1">{report.new_leads}</p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Total Found</p>
          <p className="text-3xl font-bold mt-1">{report.total_leads_found}</p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Jobs Run</p>
          <p className="text-3xl font-bold mt-1">{report.scrape_jobs_run}</p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-sm text-[var(--muted-foreground)]">Jobs Failed</p>
          <p className="text-3xl font-bold mt-1 text-[var(--destructive)]">
            {report.scrape_jobs_failed}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
          <h3 className="font-semibold mb-4">By Source</h3>
          {Object.keys(report.leads_by_source).length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">No data</p>
          ) : (
            <div className="space-y-2">
              {Object.entries(report.leads_by_source)
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .map(([source, count]) => (
                  <div key={source} className="flex items-center gap-3">
                    <span className="text-sm capitalize w-28">{source}</span>
                    <div className="flex-1 bg-[var(--muted)] rounded-full h-4">
                      <div
                        className="bg-[var(--primary)] rounded-full h-4"
                        style={{
                          width: `${((count as number) / report.new_leads) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-sm font-mono w-8 text-right">
                      {count as number}
                    </span>
                  </div>
                ))}
            </div>
          )}
        </div>

        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
          <h3 className="font-semibold mb-4">By Location</h3>
          {Object.keys(report.leads_by_location).length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">No data</p>
          ) : (
            <div className="space-y-2">
              {Object.entries(report.leads_by_location)
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .map(([location, count]) => (
                  <div key={location} className="flex items-center justify-between">
                    <span className="text-sm">{location}</span>
                    <span className="text-sm font-mono">{count as number}</span>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>

      {report.top_hiring_positions.length > 0 && (
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5 mt-4">
          <h3 className="font-semibold mb-4">Top Hiring Positions</h3>
          <div className="space-y-2">
            {report.top_hiring_positions.map((pos, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span>{pos.title}</span>
                <span className="font-mono">{pos.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
