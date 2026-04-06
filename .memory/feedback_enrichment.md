---
name: Enrichment stack — Apollo + Hunter + free fallbacks
description: Use Apollo.io as primary enrichment (free tier org enrich, paid for people search), Hunter.io as secondary for HR emails, plus free fallbacks
type: feedback
---

Enrichment pipeline priority order:
1. Apollo.io — org enrich (free tier) for domain + company phone; people search for HR contacts (requires paid plan $49/mo)
2. Hunter.io — `department=hr` filter for recruiter emails (free tier: 50 searches/mo, new key: ec9be7c8...)
3. DuckDuckGo dorking — no CAPTCHAs, search for leaked recruiter emails
4. Google dorking — search for `"@domain" recruiter OR hr`
5. SMTP functional mailbox verify — check hr@, careers@, recruitment@ etc.
6. Google search contacts — company phone numbers + emails
7. Contact page scraping — phones/emails from company website

**Why:** User wants legit recruiter/HR emails and phone numbers. Apollo free tier doesn't include people search API. Hunter free tier is 50 searches/month. Free fallbacks cover the gap.

**How to apply:** Always try API sources first (Apollo, Hunter), fall through to free methods. All phone numbers must pass Indian phone validator. Filter junk emails (URL artifacts, placeholders, short local parts).
