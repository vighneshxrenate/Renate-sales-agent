"use client";

import { use } from "react";
import Link from "next/link";
import { useReport } from "@/hooks/useReports";
import { formatDate } from "@/lib/utils";
import { Card, StatCard } from "@/components/ui/Card";
import { SOURCE_COLORS } from "@/lib/constants";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

export default function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: report, isLoading } = useReport(id);

  if (isLoading)
    return <p className="text-[var(--muted-foreground)]">Loading...</p>;
  if (!report) return <p>Report not found</p>;

  const sourceData = Object.entries(report.leads_by_source)
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({
      name: name.replace("_", " "),
      value,
      fill: SOURCE_COLORS[name] || "var(--primary)",
    }));

  const locationData = Object.entries(report.leads_by_location)
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({ name, value }));

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
        <StatCard label="New Leads" value={report.new_leads} />
        <StatCard label="Total Found" value={report.total_leads_found} />
        <StatCard label="Jobs Run" value={report.scrape_jobs_run} />
        <StatCard
          label="Jobs Failed"
          value={report.scrape_jobs_failed}
          className={
            report.scrape_jobs_failed > 0
              ? "[&>p:nth-child(2)]:text-[var(--destructive)]"
              : ""
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-5">
          <h3 className="font-semibold mb-4">By Source</h3>
          {sourceData.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">No data</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={sourceData} layout="vertical">
                <XAxis
                  type="number"
                  stroke="var(--muted-foreground)"
                  fontSize={12}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={90}
                  stroke="var(--muted-foreground)"
                  fontSize={12}
                  style={{ textTransform: "capitalize" }}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                  }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {sourceData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="font-semibold mb-4">By Location</h3>
          {locationData.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">No data</p>
          ) : (
            <div className="space-y-2">
              {locationData.map(({ name, value }) => (
                <div
                  key={name}
                  className="flex items-center justify-between text-sm"
                >
                  <span>{name}</span>
                  <span className="font-mono">{value}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {report.top_hiring_positions.length > 0 && (
        <Card className="p-5 mt-4">
          <h3 className="font-semibold mb-4">Top Hiring Positions</h3>
          <div className="space-y-2">
            {report.top_hiring_positions.map((pos, i) => (
              <div
                key={i}
                className="flex items-center justify-between text-sm"
              >
                <span>{pos.title}</span>
                <span className="font-mono">{pos.count}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
