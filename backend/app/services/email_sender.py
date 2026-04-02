import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.config import settings
from app.models.report import DailyReport

logger = structlog.get_logger()


def _build_report_html(report: DailyReport) -> str:
    source_rows = ""
    for source, count in (report.leads_by_source or {}).items():
        source_rows += f"<tr><td style='padding:4px 12px'>{source}</td><td style='padding:4px 12px;text-align:right'>{count}</td></tr>"

    location_rows = ""
    for loc, count in (report.leads_by_location or {}).items():
        location_rows += f"<tr><td style='padding:4px 12px'>{loc}</td><td style='padding:4px 12px;text-align:right'>{count}</td></tr>"

    return f"""
    <html><body style="font-family:system-ui,sans-serif;color:#333;max-width:600px;margin:0 auto">
    <h2 style="color:#3b82f6">Renate Daily Report — {report.report_date}</h2>
    <table style="border-collapse:collapse;width:100%;margin:16px 0">
      <tr><td style="padding:8px;background:#f3f4f6"><strong>New Leads</strong></td><td style="padding:8px;background:#f3f4f6;text-align:right"><strong>{report.new_leads}</strong></td></tr>
      <tr><td style="padding:8px">Total Found</td><td style="padding:8px;text-align:right">{report.total_leads_found}</td></tr>
      <tr><td style="padding:8px;background:#f3f4f6">Jobs Run</td><td style="padding:8px;background:#f3f4f6;text-align:right">{report.scrape_jobs_run}</td></tr>
      <tr><td style="padding:8px">Jobs Failed</td><td style="padding:8px;text-align:right;color:{'#ef4444' if report.scrape_jobs_failed else '#333'}">{report.scrape_jobs_failed}</td></tr>
    </table>
    {"<h3>By Source</h3><table style='border-collapse:collapse;width:100%'>" + source_rows + "</table>" if source_rows else ""}
    {"<h3>By Location</h3><table style='border-collapse:collapse;width:100%'>" + location_rows + "</table>" if location_rows else ""}
    <hr style="margin:24px 0;border:none;border-top:1px solid #e5e7eb">
    <p style="color:#9ca3af;font-size:12px">Sent by Renate Sales Agent</p>
    </body></html>
    """


async def send_report_email(report: DailyReport) -> bool:
    if not settings.smtp_username or not settings.report_recipients:
        logger.info("email_skipped", reason="SMTP or recipients not configured")
        return False

    recipients = [r.strip() for r in settings.report_recipients.split(",") if r.strip()]
    if not recipients:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Renate Daily Report — {report.report_date} ({report.new_leads} new leads)"
    msg["From"] = settings.smtp_username
    msg["To"] = ", ".join(recipients)

    html = _build_report_html(report)
    msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=True,
        )
        logger.info("report_email_sent", recipients=recipients, date=str(report.report_date))
        return True
    except Exception:
        logger.exception("report_email_failed")
        return False
