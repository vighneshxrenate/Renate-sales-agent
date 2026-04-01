import json
import re

import anthropic
import structlog

from app.config import settings

logger = structlog.get_logger()

EXTRACTION_PROMPT = """You are a data extraction expert. Extract structured company and job listing data from the provided HTML content.

Return a JSON object with this exact structure:
{
  "companies": [
    {
      "company_name": "string (required)",
      "location": "string or null - city, state/country",
      "website": "string or null - company website URL",
      "industry": "string or null",
      "company_size": "string or null - e.g. '50-200', '1000+'",
      "description": "string or null - brief company description",
      "confidence_score": 0.0-1.0,
      "emails": [
        {"email": "string", "email_type": "generic|personal|hr|careers"}
      ],
      "phones": [
        {"phone": "string", "phone_type": "main|hr|mobile"}
      ],
      "positions": [
        {
          "title": "string (required)",
          "department": "string or null",
          "location": "string or null",
          "job_type": "string or null - full-time|part-time|contract|intern",
          "experience_level": "string or null - entry|mid|senior|lead|executive",
          "salary_range": "string or null",
          "posted_date": "string or null - YYYY-MM-DD format",
          "source_url": "string or null"
        }
      ]
    }
  ]
}

Rules:
- Extract ALL unique companies found in the HTML
- Normalize company names (remove "Inc.", "Ltd.", "Pvt." suffixes for consistency but keep the full name)
- Extract any visible email addresses or phone numbers
- If a company appears multiple times with different positions, merge into one entry
- Set confidence_score based on how complete/reliable the extracted data is
- For Indian locations, include the city name (Bangalore, Mumbai, Delhi, etc.)
- Return valid JSON only, no markdown or explanation"""


class AIExtractionService:
    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def extract_leads(self, html: str, source_url: str, source_name: str) -> list[dict]:
        if not settings.anthropic_api_key:
            logger.warning("ai_extraction.no_api_key")
            return []

        truncated = self._truncate_html(html)

        try:
            response = await self._client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": f"Extract company and job listing data from this {source_name} page ({source_url}):\n\n{truncated}",
                    }
                ],
                system=EXTRACTION_PROMPT,
            )

            text = response.content[0].text
            parsed = self._parse_response(text)

            for company in parsed:
                company["source"] = source_name
                company["source_url"] = source_url

            logger.info(
                "ai_extraction.success",
                source=source_name,
                companies_found=len(parsed),
            )
            return parsed

        except anthropic.RateLimitError:
            logger.warning("ai_extraction.rate_limited")
            return []
        except Exception:
            logger.exception("ai_extraction.failed", source_url=source_url)
            return []

    def _truncate_html(self, html: str, max_chars: int = 100_000) -> str:
        cleaned = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars]
        return cleaned

    def _parse_response(self, text: str) -> list[dict]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                logger.error("ai_extraction.parse_failed")
                return []

        if isinstance(data, dict) and "companies" in data:
            return data["companies"]
        if isinstance(data, list):
            return data
        return []
