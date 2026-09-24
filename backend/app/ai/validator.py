"""Grounding checks applied to every AI-written summary before it is shown.

1. **Numbers** — every number in the text must exist in the fact sheet (whole-number rounding
   allowed). This catches invented statistics, times and counts.
2. **Causal language** — phrases that claim causation are rejected.
3. **Zones** — the AI may only describe zones that exist and are not GREEN.
"""

import re

from app.ai.llm import SummaryOut

CAUSAL_PATTERNS = re.compile(
    r"\b(caused|causing|causes|because of|due to|led to|leads to|leading to|resulted in|"
    r"results in|triggered|triggers|is responsible for|are responsible for|was responsible for|"
    r"thanks to|as a result of)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")


def _collect_numbers(obj, out: set[str]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(_canon(obj))
        out.add(_canon(round(obj)))
        out.add(_canon(abs(obj)))
        out.add(_canon(abs(round(obj))))
    elif isinstance(obj, str):
        for m in _NUMBER.findall(obj):
            v = float(m)
            out.update({_canon(v), _canon(round(v)), _canon(abs(v)), _canon(abs(round(v)))})
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numbers(v, out)


def _canon(v: float) -> str:
    return f"{float(v):g}"


def allowed_numbers(facts: dict) -> set[str]:
    allowed: set[str] = set()
    _collect_numbers(facts, allowed)
    allowed.update(_canon(n) for n in range(0, 6))  # zone numbers and small counts ("two zones")
    return allowed


def validate(summary: SummaryOut, facts: dict) -> list[str]:
    """Return a list of problems. Empty list = safe to show."""
    problems: list[str] = []
    allowed = allowed_numbers(facts)
    texts = [summary.headline, summary.whats_happening, summary.why_it_may_matter,
             summary.possible_connection]
    for z in summary.zones:
        texts += [z.whats_happening, z.why_it_may_matter, z.possible_connection]

    for text in texts:
        for m in _NUMBER.findall(text):
            if _canon(abs(float(m))) not in allowed:
                problems.append(f"number not in facts: {m}")
        hit = CAUSAL_PATTERNS.search(text)
        if hit:
            problems.append(f"causal language: {hit.group(0)!r}")

    non_green = {z["zone_id"] for z in facts["zones"] if z["status"] != "GREEN"}
    for z in summary.zones:
        if z.zone_id not in non_green:
            problems.append(f"unexpected zone {z.zone_id}")
    return problems
