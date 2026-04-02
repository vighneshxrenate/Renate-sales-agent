import re
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import fuzz

from app.models.lead import Lead, LeadEmail, LeadPhone
from app.models.job_position import HiringPosition
from app.services.ai_extraction import ExtractedLead

COMPANY_SUFFIXES = re.compile(
    r"\b(pvt|private|ltd|limited|inc|incorporated|llp|llc|corp|corporation|co|company|"
    r"technologies|tech|solutions|services|systems|consulting|consultants|infotech|"
    r"software|india|global)\b\.?",
    re.IGNORECASE,
)

LOCATION_ALIASES: dict[str, str] = {
    "bengaluru": "bangalore",
    "mumbai": "mumbai",
    "bombay": "mumbai",
    "new delhi": "delhi",
    "ncr": "delhi",
    "gurgaon": "gurugram",
    "gurugram": "gurugram",
    "noida": "noida",
    "chennai": "chennai",
    "madras": "chennai",
    "hyderabad": "hyderabad",
    "pune": "pune",
    "kolkata": "kolkata",
    "calcutta": "kolkata",
    "ahmedabad": "ahmedabad",
    "thiruvananthapuram": "trivandrum",
}

FUZZY_THRESHOLD = 85


def normalize_company_name(name: str) -> str:
    normalized = name.lower().strip()
    normalized = COMPANY_SUFFIXES.sub("", normalized)
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def normalize_location(location: str | None) -> str | None:
    if not location:
        return None
    loc = location.lower().strip()
    # Extract city from "City, State, Country" format
    city = loc.split(",")[0].strip()
    return LOCATION_ALIASES.get(city, city)


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


async def find_duplicate(
    db: AsyncSession,
    company_name_normalized: str,
    location_normalized: str | None,
    website: str | None,
) -> Lead | None:
    # 1. Exact match on normalized name + location
    query = select(Lead).where(
        Lead.company_name_normalized == company_name_normalized,
        Lead.merged_into_id.is_(None),
    )
    if location_normalized:
        query = query.where(Lead.location_normalized == location_normalized)

    result = await db.execute(query)
    exact = result.scalar_one_or_none()
    if exact:
        return exact

    # 2. Domain match
    domain = extract_domain(website)
    if domain:
        result = await db.execute(
            select(Lead).where(
                Lead.website.ilike(f"%{domain}%"),
                Lead.merged_into_id.is_(None),
            ).limit(1)
        )
        domain_match = result.scalar_one_or_none()
        if domain_match:
            return domain_match

    # 3. Fuzzy match on name
    candidates = await db.execute(
        select(Lead).where(Lead.merged_into_id.is_(None)).limit(500)
    )
    for lead in candidates.scalars():
        score = fuzz.token_sort_ratio(company_name_normalized, lead.company_name_normalized)
        if score >= FUZZY_THRESHOLD:
            return lead

    return None


async def merge_leads(
    db: AsyncSession, existing: Lead, new_data: ExtractedLead
) -> Lead:
    # Update fields if existing has None but new has data
    if not existing.website and new_data.website:
        existing.website = new_data.website
    if not existing.industry and new_data.industry:
        existing.industry = new_data.industry
    if not existing.company_size and new_data.company_size:
        existing.company_size = new_data.company_size
    if not existing.description and new_data.description:
        existing.description = new_data.description

    # Merge emails (avoid duplicates)
    existing_emails = {e.email.lower() for e in existing.emails} if existing.emails else set()
    for email_str, email_type in new_data.emails:
        if email_str.lower() not in existing_emails:
            db.add(LeadEmail(
                lead_id=existing.id, email=email_str, email_type=email_type, source="scraped"
            ))

    # Merge phones (avoid duplicates)
    existing_phones = {p.phone for p in existing.phones} if existing.phones else set()
    for phone_str, phone_type in new_data.phones:
        if phone_str not in existing_phones:
            db.add(LeadPhone(
                lead_id=existing.id, phone=phone_str, phone_type=phone_type
            ))

    # Merge positions (avoid duplicate titles)
    existing_titles = {p.title.lower() for p in existing.positions if p.title} if existing.positions else set()
    for pos in new_data.positions:
        title = pos.get("title", "")
        if title.lower() not in existing_titles:
            db.add(HiringPosition(
                lead_id=existing.id,
                title=title,
                department=pos.get("department"),
                location=pos.get("location"),
                job_type=pos.get("job_type"),
                experience_level=pos.get("experience_level"),
                salary_range=pos.get("salary_range"),
                source_url=pos.get("source_url"),
                raw_text=pos.get("raw_text"),
            ))

    await db.flush()
    return existing
