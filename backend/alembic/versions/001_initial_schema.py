"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable trigram extension for fuzzy search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "scrape_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("keywords", sa.String(500)),
        sa.Column("location_filter", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("triggered_by", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("total_pages", sa.Integer()),
        sa.Column("pages_scraped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_name", sa.String(500), nullable=False),
        sa.Column("company_name_normalized", sa.String(500), nullable=False),
        sa.Column("location", sa.String(500)),
        sa.Column("location_normalized", sa.String(500)),
        sa.Column("website", sa.String(2000)),
        sa.Column("industry", sa.String(200)),
        sa.Column("company_size", sa.String(50)),
        sa.Column("description", sa.Text()),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("scrape_job_id", sa.Uuid(), sa.ForeignKey("scrape_jobs.id")),
        sa.Column("merged_into_id", sa.Uuid(), sa.ForeignKey("leads.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_leads_company_name_normalized", "leads", ["company_name_normalized"])
    op.create_index("ix_leads_location_normalized", "leads", ["location_normalized"])
    op.create_index("ix_leads_dedup", "leads", ["company_name_normalized", "location_normalized"])
    # Trigram index for fuzzy search
    op.execute(
        "CREATE INDEX ix_leads_company_name_trgm ON leads USING gin (company_name gin_trgm_ops)"
    )

    op.create_table(
        "lead_emails",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lead_id", sa.Uuid(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(500), nullable=False),
        sa.Column("email_type", sa.String(20)),
        sa.Column("source", sa.String(50)),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "lead_phones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lead_id", sa.Uuid(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column("phone_type", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "hiring_positions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lead_id", sa.Uuid(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("department", sa.String(200)),
        sa.Column("location", sa.String(500)),
        sa.Column("job_type", sa.String(50)),
        sa.Column("experience_level", sa.String(50)),
        sa.Column("salary_range", sa.String(200)),
        sa.Column("posted_date", sa.Date()),
        sa.Column("source_url", sa.String(2000)),
        sa.Column("raw_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_date", sa.Date(), unique=True, nullable=False),
        sa.Column("total_leads_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_leads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_by_source", JSONB(), nullable=False, server_default="{}"),
        sa.Column("leads_by_location", JSONB(), nullable=False, server_default="{}"),
        sa.Column("top_hiring_positions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("scrape_jobs_run", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scrape_jobs_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "proxies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("protocol", sa.String(10), nullable=False, server_default="http"),
        sa.Column("host", sa.String(200), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(200)),
        sa.Column("password", sa.String(200)),
        sa.Column("provider", sa.String(50)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("cooldown_until", sa.DateTime(timezone=True)),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_response_ms", sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table("proxies")
    op.drop_table("daily_reports")
    op.drop_table("hiring_positions")
    op.drop_table("lead_phones")
    op.drop_table("lead_emails")
    op.execute("DROP INDEX IF EXISTS ix_leads_company_name_trgm")
    op.drop_table("leads")
    op.drop_table("scrape_jobs")
