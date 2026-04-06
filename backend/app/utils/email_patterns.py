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
    r"(?:"
    r"(?:\+91[\s\-]?)?(?:\(?0\d{2,4}\)?[\s\-.]?)\d{3,4}[\s\-.]?\d{3,4}"
    r"|1800[\s\-]?\d{3}[\s\-]?\d{3,4}"
    r"|\+91[\s\-]?\d{4,5}[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
    r"|\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
    r"|(?<!\d)\d{10}(?!\d)"
    r")",
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
        digits = re.sub(r"\D", "", cleaned)
        if len(set(digits)) <= 3:
            continue
        seen.add(cleaned)
        if cleaned.startswith("1800"):
            phone_type = "toll_free"
        elif cleaned.startswith("+91") and len(cleaned) == 13:
            phone_type = "mobile"
        elif len(cleaned) == 10 and cleaned[0] in "6789":
            phone_type = "mobile"
        else:
            phone_type = "main"
        results.append((phone.strip(), phone_type))
    return results
