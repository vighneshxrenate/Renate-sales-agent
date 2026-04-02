import re
from urllib.parse import urlparse


def extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc or parsed.path
        domain = domain.lower().replace("www.", "")
        return domain or None
    except Exception:
        return None


def generate_email_candidates(domain: str) -> list[tuple[str, str]]:
    """Returns list of (email, type) tuples."""
    prefixes = [
        ("info", "generic"),
        ("hr", "hr"),
        ("careers", "careers"),
        ("contact", "generic"),
        ("hiring", "hr"),
        ("jobs", "careers"),
        ("recruitment", "hr"),
        ("talent", "hr"),
        ("people", "hr"),
    ]
    return [(f"{prefix}@{domain}", email_type) for prefix, email_type in prefixes]


EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)

PHONE_REGEX = re.compile(
    r"(?:\+91[\s-]?)?(?:\(?0?\d{2,4}\)?[\s.-]?)?\d{6,10}",
)

EXCLUDE_EMAIL_PATTERNS = re.compile(
    r"@(example\.com|test\.com|sentry\.io|googleapis\.com|w3\.org|schema\.org|cloudflare)",
    re.IGNORECASE,
)


def extract_emails_from_text(text: str) -> list[tuple[str, str]]:
    matches = EMAIL_REGEX.findall(text)
    results = []
    seen = set()
    for email in matches:
        email_lower = email.lower()
        if email_lower in seen or EXCLUDE_EMAIL_PATTERNS.search(email_lower):
            continue
        seen.add(email_lower)

        if any(prefix in email_lower.split("@")[0] for prefix in ("hr", "hiring", "recruit", "talent", "people")):
            email_type = "hr"
        elif any(prefix in email_lower.split("@")[0] for prefix in ("career", "job")):
            email_type = "careers"
        elif any(prefix in email_lower.split("@")[0] for prefix in ("info", "contact", "hello", "support")):
            email_type = "generic"
        else:
            email_type = "personal"

        results.append((email, email_type))
    return results


def extract_phones_from_text(text: str) -> list[tuple[str, str]]:
    matches = PHONE_REGEX.findall(text)
    results = []
    seen = set()
    for phone in matches:
        cleaned = re.sub(r"[\s.()\-]", "", phone)
        if len(cleaned) < 8 or cleaned in seen:
            continue
        seen.add(cleaned)
        phone_type = "mobile" if cleaned.startswith("+91") or len(cleaned) == 10 else "main"
        results.append((phone, phone_type))
    return results
