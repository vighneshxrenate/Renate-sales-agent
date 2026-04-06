---
name: No Anthropic API — use OpenAI
description: User explicitly removed Anthropic SDK in favor of OpenAI GPT-4o-mini for cost reasons
type: feedback
---

Do not use Anthropic/Claude API for extraction or any AI features in this project. User chose OpenAI GPT-4o-mini for cost efficiency (~$0.15/1M input tokens).

**Why:** Cost was the deciding factor. User wanted "cost friendly yet accurate" alternatives to Claude.

**How to apply:** Any new AI features should use the existing OpenAI client (`settings.openai_api_key`, model `gpt-4o-mini`). Don't suggest or add Anthropic SDK.
