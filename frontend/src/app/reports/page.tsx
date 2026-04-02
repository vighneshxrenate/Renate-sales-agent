"use client";

import Link from "next/link";
import { useReports } from "@/hooks/useReports";
import { formatDate } from "@/lib/utils";
import { Card } from "@/components/ui/Card";

export default function ReportsPage() {
  const { data, isLoading } = useReports();

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Daily Reports</h2>

      {isLoading ? (
        <p className="text-[var(--muted-foreground)]">Loading...</p>
      ) : data?.reports.length === 0 ? (
        <p className="text-[var(--muted-foreground)]">
          No reports yet. Reports are generated daily at 9 AM after scraping
          completes.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.reports.map((report) => (
            <Link key={report.id} href={`/reports/${report.id}`}>
              <Card className="p-5 hover:border-[var(--primary)] transition-colors">
                <p className="font-semibold">
                  {formatDate(report.report_date)}
                </p>
                <div className="mt-3 space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">
                      New Leads
                    </span>
                    <span className="font-mono">{report.new_leads}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">
                      Jobs Run
                    </span>
                    <span className="font-mono">{report.scrape_jobs_run}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">
                      Failed
                    </span>
                    <span className="font-mono">
                      {report.scrape_jobs_failed}
                    </span>
                  </div>
                </div>
                {report.email_sent && (
                  <p className="text-xs text-green-400 mt-3">Email sent</p>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
