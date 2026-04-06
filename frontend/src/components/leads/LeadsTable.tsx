"use client";

import Link from "next/link";
import type { Lead } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card } from "@/components/ui/Card";

export function LeadsTable({
  leads,
  isLoading,
}: {
  leads: Lead[] | undefined;
  isLoading: boolean;
}) {
  return (
    <Card className="overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
            <th className="px-4 py-3">Company</th>
            <th className="px-4 py-3">Location</th>
            <th className="px-4 py-3">Source</th>
            <th className="px-4 py-3">Emails</th>
            <th className="px-4 py-3">Positions</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Created</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <tr>
              <td
                colSpan={7}
                className="px-4 py-8 text-center text-[var(--muted-foreground)]"
              >
                Loading...
              </td>
            </tr>
          ) : !leads || leads.length === 0 ? (
            <tr>
              <td
                colSpan={7}
                className="px-4 py-8 text-center text-[var(--muted-foreground)]"
              >
                No leads found.
              </td>
            </tr>
          ) : (
            leads.map((lead) => (
              <tr
                key={lead.id}
                className="border-b border-[var(--border)] hover:bg-[var(--muted)] transition-colors"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/leads/${lead.id}`}
                    className="text-[var(--primary)] hover:underline font-medium"
                  >
                    {lead.company_name}
                  </Link>
                </td>
                <td className="px-4 py-3">{lead.location || "—"}</td>
                <td className="px-4 py-3 capitalize">
                  {lead.source.replace("_", " ")}
                </td>
                <td className="px-4 py-3">{lead.emails.length}</td>
                <td className="px-4 py-3">{lead.positions.length}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={lead.status} />
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)]">
                  {formatDate(lead.created_at)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </Card>
  );
}
