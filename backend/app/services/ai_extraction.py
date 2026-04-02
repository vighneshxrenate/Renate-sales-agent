import json
from dataclasses import dataclass, field

import structlog
from openai import AsyncOpenAI, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = structlog.get_logger()

EXTRACTION_FUNCTION = {
    "name": "extract_leads",
    "description": "Extract structured lead data from job listing HTML",
    "parameters": {
        "type": "object",
        "properties": {
            "leads": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "location": {"type": "string"},
                        "website": {"type": "string"},
                        "industry": {"type": "string"},
                        "company_size": {"type": "string"},
                        "description": {"type": "string"},
                        "confidence_score": {"type": "number"},
                        "emails": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"},
                                    "type": {"type": "string", "enum": ["generic", "personal", "hr", "careers"]},
                                },
                                "required": ["email", "type"],
                            },
                        },
                        "phones": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "phone": {"type": "string"},
                                    "type": {"type": "string", "enum": ["main", "hr", "mobile"]},
                                },
                                "required": ["phone", "type"],
                            },
                        },
                        "positions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "department": {"type": "string"},
                                    "location": {"type": "string"},
                                    "job_type": {"type": "string"},
                                    "experience_level": {"type": "string"},
                                    "salary_range": {"type": "string"},
                                    "source_url": {"type": "string"},
                                    "raw_text": {"type": "string"},
                                },
                                "required": ["title"],
                            },
                        },
                    },
                    "required": ["company_name"],
                },
            },
        },
        "required": ["leads"],
    },
}

SOURCE_PROMPTS = {
    "google_jobs": "Extract company and job listing data from these Google Jobs search results.",
    "linkedin": "Extract company profiles and job listing data from these LinkedIn job search results.",
    "naukri": "Extract company and job listing data from these Naukri.com search results.",
    "indeed": "Extract company and job listing data from these Indeed job search results.",
    "glassdoor": "Extract company and job listing data from these Glassdoor job search results.",
    "career_page": "Extract company information and all job listings from this company careers page.",
}

MAX_HTML_LENGTH = 100_000


@dataclass
class ExtractedLead:
    company_name: str
    source: str = ""
    source_url: str = ""
    location: str | None = None
    website: str | None = None
    industry: str | None = None
    company_size: str | None = None
    description: str | None = None
    confidence_score: float = 0.5
    emails: list[tuple[str, str]] = field(default_factory=list)
    phones: list[tuple[str, str]] = field(default_factory=list)
    positions: list[dict] = field(default_factory=list)


class AIExtractionService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    async def extract_leads(self, html: str, source: str, url: str) -> list[ExtractedLead]:
        if len(html) > MAX_HTML_LENGTH:
            html = html[:MAX_HTML_LENGTH]

        source_prompt = SOURCE_PROMPTS.get(source, "Extract company and job listing data from this HTML.")

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=4096,
                temperature=0,
                tools=[{"type": "function", "function": EXTRACTION_FUNCTION}],
                tool_choice={"type": "function", "function": {"name": "extract_leads"}},
                messages=[{
                    "role": "user",
                    "content": (
                        f"{source_prompt}\n\n"
                        f"Source URL: {url}\n"
                        f"Source type: {source}\n\n"
                        "Focus on: company name, location (especially Indian cities), website, "
                        "industry, company size, any contact emails/phones, and job positions "
                        "with title, department, experience level.\n\n"
                        f"HTML content:\n{html}"
                    ),
                }],
            )
        except RateLimitError:
            logger.warning("openai_rate_limited", source=source)
            raise
        except Exception:
            logger.exception("openai_extraction_failed", source=source, url=url)
            raise

        leads: list[ExtractedLead] = []
        for choice in response.choices:
            if not choice.message.tool_calls:
                continue
            for tool_call in choice.message.tool_calls:
                if tool_call.function.name != "extract_leads":
                    continue
                try:
                    data = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    logger.warning("openai_invalid_json", source=source)
                    continue

                for raw in data.get("leads", []):
                    lead = ExtractedLead(
                        company_name=raw["company_name"],
                        source=source,
                        source_url=url,
                        location=raw.get("location"),
                        website=raw.get("website"),
                        industry=raw.get("industry"),
                        company_size=raw.get("company_size"),
                        description=raw.get("description"),
                        confidence_score=raw.get("confidence_score", 0.5),
                        emails=[(e["email"], e["type"]) for e in raw.get("emails", [])],
                        phones=[(p["phone"], p["type"]) for p in raw.get("phones", [])],
                        positions=raw.get("positions", []),
                    )
                    leads.append(lead)

        logger.info("ai_extraction_complete", source=source, leads_count=len(leads))
        return leads
