"""Unit conversions and value validation for the common data model.

Canonical units: mm/h, °C, km/h, %, minutes, µg/m³, US AQI, cm.
"""


def fahrenheit_to_celsius(f: float) -> float:
    return (f - 32) * 5 / 9


def ms_to_kmh(ms: float) -> float:
    return ms * 3.6


def per_interval_to_per_hour(amount: float, interval_minutes: float) -> float:
    return amount * 60 / interval_minutes


def mm_to_cm(mm: float) -> float:
    return mm / 10


# US EPA PM2.5 breakpoints (24h, 2024 revision): (C_low, C_high, I_low, I_high)
_PM25_BREAKPOINTS = (
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
)


def pm25_to_us_aqi(pm25: float) -> float:
    """Linear interpolation inside the EPA breakpoint table."""
    c = max(0.0, round(pm25, 1))
    for c_lo, c_hi, i_lo, i_hi in _PM25_BREAKPOINTS:
        if c <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (c - c_lo) + i_lo)
    return 500.0


# Physically plausible ranges. Values outside are rejected as malformed.
VALID_RANGES: dict[str, tuple[float, float]] = {
    "rain_mm_h": (0, 300),
    "temperature_c": (-30, 60),
    "wind_kmh": (0, 250),
    "congestion_pct": (0, 100),
    "avg_speed_kmh": (0, 150),
    "transit_delay_min": (-10, 180),
    "pm25_ugm3": (0, 1000),
    "aqi": (0, 500),
    "water_level_cm": (0, 300),
}


def validate_value(metric: str, value: object) -> float:
    """Return ``value`` as a float or raise ``ValueError`` if missing/invalid/out of range."""
    if value is None or isinstance(value, bool):
        raise ValueError(f"{metric}: missing value")
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{metric}: not a number ({value!r})") from exc
    if v != v:  # NaN
        raise ValueError(f"{metric}: NaN")
    lo, hi = VALID_RANGES.get(metric, (float("-inf"), float("inf")))
    if not lo <= v <= hi:
        raise ValueError(f"{metric}: {v} outside plausible range [{lo}, {hi}]")
    return v
