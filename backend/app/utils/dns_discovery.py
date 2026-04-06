import asyncio
import socket

import dns.resolver
import structlog

logger = structlog.get_logger()


async def verify_domain_has_mx(domain: str) -> bool:
    try:
        result = await asyncio.to_thread(_resolve_mx, domain)
        return len(result) > 0
    except Exception:
        return False


def _resolve_mx(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX")
        return [str(r.exchange) for r in answers]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return []
    except Exception:
        return []


async def verify_email_smtp(email: str) -> bool:
    """Basic SMTP verification — connect to MX server and check RCPT TO.

    Note: Many servers accept all RCPT TO (catch-all), so a True result
    doesn't guarantee the email exists. A rejection is more reliable.
    """
    domain = email.split("@")[1]
    mx_records = await asyncio.to_thread(_resolve_mx, domain)
    if not mx_records:
        return False

    mx_host = mx_records[0].rstrip(".")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_smtp_check, mx_host, email),
            timeout=15,
        )
        return result
    except (TimeoutError, asyncio.TimeoutError):
        logger.debug("smtp_verify_timeout", email=email)
        return False
    except Exception:
        logger.debug("smtp_verify_failed", email=email)
        return False


def _smtp_check(mx_host: str, email: str) -> bool:
    import smtplib

    try:
        with smtplib.SMTP(mx_host, 25, timeout=10) as smtp:
            smtp.ehlo("verify.local")
            smtp.mail("verify@verify.local")
            code, _ = smtp.rcpt(email)
            return code == 250
    except Exception:
        return False
