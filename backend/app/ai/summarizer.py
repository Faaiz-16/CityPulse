"""Produces the plain-language summary shown in the UI.

1. The deterministic template summary is built on every tick (instant, always correct).
2. If an API key is configured and the *situation* changed (see ``facts.fingerprint``), an LLM
   rewrite is requested in a background thread so the pipeline never waits for it.
3. The LLM answer is shown only if it passes the grounding validator AND still matches the
   current situation. Otherwise the template stays on screen.
"""

import logging
import threading
import time
from datetime import UTC, datetime

from app.ai import llm, templates
from app.ai.facts import build_facts, fingerprint
from app.ai.validator import validate
from app.config import Settings
from app.schemas import FeedHealth, FeedStatus, Summary, SummarySection, ZoneState

log = logging.getLogger("citypulse.ai")


class Summarizer:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._lock = threading.Lock()
        self._ai: dict | None = None  # {"fingerprint", "summary": llm.SummaryOut, "at"}
        self._inflight = False
        self._last_call = 0.0
        self.last_error: str | None = None
        self.ai_calls = 0
        self.ai_rejections = 0

    @property
    def status(self) -> str:
        if not self.s.ai_enabled:
            return "disabled (no API key) — using templates"
        if self.last_error:
            return f"fallback to templates ({self.last_error})"
        return "ready"

    def summarize(self, zones: list[ZoneState], feeds: list[FeedHealth], now: datetime
                  ) -> tuple[Summary, dict[str, SummarySection]]:
        degraded = [f.label.lower() for f in feeds if f.status not in (FeedStatus.LIVE, FeedStatus.SIMULATED)]
        headline, sections = templates.city_summary(zones, degraded)
        zone_sections = {z.id: templates.zone_explanation(z) for z in zones}
        summary = Summary(headline=headline, sections=sections, generated_by="template", generated_at=now)

        if not self.s.ai_enabled:
            return summary, zone_sections

        facts = build_facts(zones, feeds, now, self.s.tz, self.s.rolling_window_minutes)
        fp = fingerprint(facts)
        with self._lock:
            cached = self._ai if self._ai and self._ai["fingerprint"] == fp else None
        if cached:
            out: llm.SummaryOut = cached["summary"]
            summary = Summary(
                headline=out.headline,
                sections=SummarySection(whats_happening=out.whats_happening,
                                        why_it_matters=out.why_it_may_matter,
                                        possible_connection=out.possible_connection),
                generated_by="ai", generated_at=cached["at"],
                note="AI-assisted wording, generated only from CityPulse's analysed data and checked "
                     "automatically. Figures are as of the time shown.",
            )
            for z in out.zones:
                zone_sections[z.zone_id] = SummarySection(
                    whats_happening=z.whats_happening, why_it_matters=z.why_it_may_matter,
                    possible_connection=z.possible_connection)
        else:
            self._maybe_request(facts, fp)
        return summary, zone_sections

    def _maybe_request(self, facts: dict, fp: str) -> None:
        with self._lock:
            if self._inflight or time.monotonic() - self._last_call < self.s.ai_min_interval_seconds:
                return
            self._inflight = True
            self._last_call = time.monotonic()
        threading.Thread(target=self._run, args=(facts, fp), daemon=True).start()

    def _run(self, facts: dict, fp: str) -> None:
        try:
            self.ai_calls += 1
            out = llm.generate(facts, self.s.anthropic_api_key, self.s.ai_model, self.s.ai_timeout_seconds)
            if out is None:
                self.last_error = "AI service unavailable"
                return
            problems = validate(out, facts)
            if problems:
                self.ai_rejections += 1
                self.last_error = "AI text failed grounding checks"
                log.warning("AI summary rejected: %s", problems[:3])
                return
            self.last_error = None
            with self._lock:
                self._ai = {"fingerprint": fp, "summary": out, "at": datetime.now(UTC)}
        finally:
            with self._lock:
                self._inflight = False
