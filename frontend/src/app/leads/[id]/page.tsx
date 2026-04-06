"use client";

import { use } from "react";
import Link from "next/link";
import { useLead, useUpdateLead } from "@/hooks/useLeads";
import { formatDateTime } from "@/lib/utils";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  STATUSES,
  EMAIL_SOURCE_LABELS,
  EMAIL_TYPE_LABELS,
} from "@/lib/constants";

export default function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: lead, isLoading } = useLead(id);
  const updateLead = useUpdateLead();

  if (isLoading)
    return <p className="text-[var(--muted-foreground)]">Loading...</p>;
  if (!lead) return <p>Lead not found</p>;

  return (
    <div>
      <Link
        href="/leads"
        className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] mb-4 inline-block"
      >
        &larr; Back to Leads
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">{lead.company_name}</h2>
          <p className="text-[var(--muted-foreground)]">
            {lead.location || "Location unknown"} &middot;{" "}
            <span className="capitalize">{lead.source.replace("_", " ")}</span>
          </p>
        </div>
        <select
          value={lead.status}
          onChange={(e) =>
            updateLead.mutate({ id: lead.id, data: { status: e.target.value } })
          }
          className="bg-[var(--muted)] border border-[var(--border)] rounded-lg px-3 py-1.5 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Company Info</h3>
          <dl className="space-y-2 text-sm">
            {lead.website && (
              <>
                <dt className="text-[var(--muted-foreground)]">Website</dt>
                <dd>
                  <a
                    href={lead.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[var(--primary)] hover:underline"
                  >
                    {lead.website}
                  </a>
                </dd>
              </>
            )}
            {lead.industry && (
              <>
                <dt className="text-[var(--muted-foreground)]">Industry</dt>
                <dd>{lead.industry}</dd>
              </>
            )}
            {lead.company_size && (
              <>
                <dt className="text-[var(--muted-foreground)]">Size</dt>
                <dd>{lead.company_size}</dd>
              </>
            )}
            {lead.confidence_score != null && (
              <>
                <dt className="text-[var(--muted-foreground)]">Confidence</dt>
                <dd>{Math.round(lead.confidence_score * 100)}%</dd>
              </>
            )}
            <dt className="text-[var(--muted-foreground)]">Source URL</dt>
            <dd>
              <a
                href={lead.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--primary)] hover:underline break-all"
              >
                {lead.source_url}
              </a>
            </dd>
            <dt className="text-[var(--muted-foreground)]">Created</dt>
            <dd>{formatDateTime(lead.created_at)}</dd>
          </dl>
        </Card>

        <Card className="p-5">
          <h3 className="font-semibold mb-3">
            Emails ({lead.emails.length})
          </h3>
          {lead.emails.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No emails discovered yet.
            </p>
          ) : (
            <ul className="space-y-2">
              {lead.emails.map((e) => (
                <li key={e.id} className="text-sm">
                  <a
                    href={`mailto:${e.email}`}
                    className="text-[var(--primary)] hover:underline"
                  >
                    {e.email}
                  </a>
                  <div className="flex gap-2 mt-0.5">
                    {e.email_type && (
                      <span className="text-xs bg-[var(--muted)] px-1.5 py-0.5 rounded">
                        {EMAIL_TYPE_LABELS[e.email_type] || e.email_type}
                      </span>
                    )}
                    {e.source && (
                      <span className="text-xs bg-[var(--muted)] px-1.5 py-0.5 rounded">
                        {EMAIL_SOURCE_LABELS[e.source] || e.source}
                      </span>
                    )}
                    <span
                      className={`text-xs ${e.verified ? "text-green-400" : "text-[var(--muted-foreground)]"}`}
                    >
                      {e.verified ? "verified" : "unverified"}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="font-semibold mb-3">
            Phones ({lead.phones.length})
          </h3>
          {lead.phones.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No phone numbers discovered yet.
            </p>
          ) : (
            <ul className="space-y-2">
              {lead.phones.map((p) => (
                <li key={p.id} className="text-sm">
                  <a
                    href={`tel:${p.phone}`}
                    className="text-[var(--primary)] hover:underline"
                  >
                    {p.phone}
                  </a>
                  {p.phone_type && (
                    <span className="text-[var(--muted-foreground)] ml-2 text-xs">
                      {p.phone_type}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="p-5">
        <h3 className="font-semibold mb-3">
          Hiring Positions ({lead.positions.length})
        </h3>
        {lead.positions.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">
            No positions found.
          </p>
        ) : (
          <div className="space-y-3">
            {lead.positions.map((pos) => (
              <div
                key={pos.id}
                className="flex items-center justify-between border-b border-[var(--border)] pb-3 last:border-0"
              >
                <div>
                  <p className="font-medium text-sm">{pos.title}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {[pos.department, pos.location, pos.job_type]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                {pos.experience_level && (
                  <span className="text-xs bg-[var(--muted)] px-2 py-1 rounded">
                    {pos.experience_level}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
