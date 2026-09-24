"""Turn every timestamp convention used by the feeds into timezone-aware UTC.

Feeds disagree about time:
  * ISO-8601 with an offset            "2026-09-24T15:07:30+05:30"
  * ISO-8601 "Z" (UTC)                 "2026-09-24T09:37:30Z"
  * ISO-8601 with no zone (local time) "2026-09-24T15:07"
  * epoch seconds / epoch milliseconds 1790000000 / 1790000000000
  * day-first local text               "24/09/2026 15:07"
  * local text with a zone name        "2026-09-24 15:07:33 IST"

Everything is stored and compared in UTC; the UI converts back to local time for display.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


class TimestampError(ValueError):
    pass


_ZONE_ABBREVIATIONS = {"IST": "Asia/Kolkata", "UTC": "UTC", "GMT": "UTC"}
MAX_FUTURE_SKEW = timedelta(minutes=5)


def parse_timestamp(value: object, local_tz: ZoneInfo, *, now: datetime | None = None) -> datetime:
    """Parse ``value`` into an aware UTC datetime. Raises ``TimestampError`` if impossible."""
    if value is None or value == "":
        raise TimestampError("missing timestamp")

    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=local_tz)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = value / 1000 if value > 1e11 else value  # ms vs s
        dt = datetime.fromtimestamp(seconds, tz=UTC)
    elif isinstance(value, str):
        dt = _parse_text(value.strip(), local_tz)
    else:
        raise TimestampError(f"unsupported timestamp type {type(value).__name__}")

    dt = dt.astimezone(UTC)
    if now is not None and dt - now > MAX_FUTURE_SKEW:
        raise TimestampError("timestamp is in the future")
    return dt


def _parse_text(text: str, local_tz: ZoneInfo) -> datetime:
    # "2026-09-24 15:07:33 IST"
    parts = text.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].upper() in _ZONE_ABBREVIATIONS:
        tz = ZoneInfo(_ZONE_ABBREVIATIONS[parts[1].upper()])
        try:
            return datetime.fromisoformat(parts[0]).replace(tzinfo=tz)
        except ValueError as exc:
            raise TimestampError(f"bad timestamp {text!r}") from exc

    # "24/09/2026 15:07" (day-first, local time)
    if "/" in text:
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=local_tz)
            except ValueError:
                continue
        raise TimestampError(f"bad timestamp {text!r}")

    # ISO-8601 variants
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TimestampError(f"bad timestamp {text!r}") from exc
    return dt if dt.tzinfo else dt.replace(tzinfo=local_tz)
