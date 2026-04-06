"use client";

import { useLeadStats } from "@/hooks/useLeads";
import { useJobs } from "@/hooks/useJobs";
import { StatCard, Card } from "@/components/ui/Card";
import { SOURCE_COLORS } from "@/lib/constants";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from "recharts";

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useLeadStats();
  const { data: jobsData } = useJobs({ page: 1 });

  const runningJobs =
    jobsData?.jobs.filter((j) => j.status === "running").length ?? 0;

  const sourceData = Object.entries(stats?.by_source ?? {}).map(
    ([name, value]) => ({
      name: name.replace("_", " "),
      value,
      fill: SOURCE_COLORS[name] || "var(--primary)",
    })
  );

  const statusData = Object.entries(stats?.by_status ?? {}).map(
    ([name, value]) => ({ name, value })
  );

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
          value={
            statsLoading ? "..." : Object.keys(stats?.by_source ?? {}).length
          }
        />
        <StatCard
          label="New Leads"
          value={statsLoading ? "..." : (stats?.by_status?.new ?? 0)}
          sub="awaiting review"
        />
      </div>

      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="p-5">
            <h3 className="font-semibold mb-4">Leads by Source</h3>
            {sourceData.length === 0 ? (
              <p className="text-[var(--muted-foreground)] text-sm">
                No leads yet. Trigger a scrape job to get started.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={sourceData} layout="vertical">
                  <XAxis type="number" stroke="var(--muted-foreground)" fontSize={12} />
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
            <h3 className="font-semibold mb-4">Leads by Status</h3>
            {statusData.length === 0 ? (
              <p className="text-[var(--muted-foreground)] text-sm">
                No leads yet.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={statusData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={3}
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    <Cell fill="#3b82f6" />
                    <Cell fill="#f59e0b" />
                    <Cell fill="#22c55e" />
                    <Cell fill="#ef4444" />
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
