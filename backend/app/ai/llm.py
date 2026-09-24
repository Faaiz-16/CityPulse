"""Optional LLM rewrite of the structured facts into friendlier plain language.

The model receives ONLY the fact sheet from ``facts.py`` and must return a fixed JSON shape
(enforced with structured outputs). Its answer is then checked by ``validator.py``; anything
that fails is thrown away and the deterministic template is shown instead.
"""

import json
import logging

import anthropic
from pydantic import BaseModel

log = logging.getLogger("citypulse.ai")


class ZoneExplanationOut(BaseModel):
    zone_id: str
    whats_happening: str
    why_it_may_matter: str
    possible_connection: str


class SummaryOut(BaseModel):
    headline: str
    whats_happening: str
    why_it_may_matter: str
    possible_connection: str
    zones: list[ZoneExplanationOut]


SYSTEM_PROMPT = """You write the public "right now" summary for CityPulse, a civic dashboard that \
residents glance at to understand their city. You are given a JSON fact sheet produced by \
CityPulse's analysis engine. It is the only source of truth.

Rules:
- Use only facts in the sheet. Do not add events, places, times, causes or numbers that are not in it. \
Every number you write must appear in the sheet (you may round it to a whole number).
- Relationships are possible links, never causes. Use wording like "may be related", \
"possible connection", "signals suggest", "conditions are consistent with". Never say one thing \
caused, led to, triggered or was due to another.
- If the sheet lists insufficient evidence or something that cannot be assessed, say so plainly.
- If a feed is degraded, mention that some information is unavailable.
- Write for a non-technical resident: short sentences, no jargon, no statistics terms.
- headline: one sentence, at most 20 words.
- whats_happening / why_it_may_matter / possible_connection: 1–3 sentences each, city-wide.
- zones: one entry for every zone whose status is not GREEN, using its zone_id; empty list if none."""


def generate(facts: dict, api_key: str, model: str, timeout: float) -> SummaryOut | None:
    """Call the Claude API. Returns None on any failure (the caller falls back to templates)."""
    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=1)
        response = client.messages.parse(
            model=model,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "Fact sheet:\n" + json.dumps(facts, default=str)}],
            output_format=SummaryOut,
        )
    except anthropic.AuthenticationError:
        log.warning("AI summary disabled for this call: invalid API key")
        return None
    except anthropic.RateLimitError:
        log.warning("AI summary skipped: rate limited")
        return None
    except anthropic.APIStatusError as exc:
        log.warning("AI summary failed: HTTP %s", exc.status_code)
        return None
    except anthropic.APIConnectionError:
        log.warning("AI summary failed: connection error or timeout")
        return None
    except Exception:  # never let the explanation layer take anything else down
        log.exception("AI summary failed unexpectedly")
        return None

    if response.stop_reason == "refusal" or response.parsed_output is None:
        log.warning("AI summary unusable (stop_reason=%s)", response.stop_reason)
        return None
    return response.parsed_output
