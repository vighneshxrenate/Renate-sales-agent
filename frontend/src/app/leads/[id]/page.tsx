"use client";

import { use } from "react";
import Link from "next/link";
import { useLead } from "@/hooks/useLeads";
import { formatDateTime } from "@/lib/utils";

export default function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: lead, isLoading } = useLead(id);

  if (isLoading) return <p className="text-[var(--muted-foreground)]">Loading...</p>;
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
            <span className="capitalize">{lead.source}</span>
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded text-sm font-medium ${
            lead.status === "new"
              ? "bg-blue-500/20 text-blue-400"
              : lead.status === "qualified"
                ? "bg-green-500/20 text-green-400"
                : "bg-yellow-500/20 text-yellow-400"
          }`}
        >
          {lead.status}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
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
        </div>

        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
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
                  <span className="text-[var(--muted-foreground)] ml-2">
                    {e.email_type} &middot; {e.verified ? "verified" : "unverified"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
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
                    <span className="text-[var(--muted-foreground)] ml-2">
                      {p.phone_type}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
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
      </div>
    </div>
  );
}
