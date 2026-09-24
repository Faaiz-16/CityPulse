"""Application configuration.

All settings can be overridden with environment variables prefixed ``CITYPULSE_``
(or via ``backend/.env``). Defaults are chosen so the app runs with no configuration.
"""

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CITYPULSE_", env_file=".env", extra="ignore"
    )

    # --- Infrastructure ---
    database_url: str = "sqlite:///./data/citypulse.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    tick_seconds: float = 3.0
    run_background_loop: bool = True  # tests switch this off and drive ticks manually
    frontend_dist: str = ""  # built frontend to serve; empty = ../frontend/dist if it exists

    # --- Demo city ---
    city_name: str = "Jaipur"
    city_timezone: str = "Asia/Kolkata"
    history_days: int = 3  # synthetic history used to learn baselines
    random_seed: int = 42

    # --- External data ---
    live_apis: bool = False
    api_timeout_seconds: float = 4.0
    live_refresh_seconds: int = 600  # Open-Meteo updates every 15 min; don't hammer it

    # --- AI ---
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    ai_model: str = "claude-opus-5"
    ai_timeout_seconds: float = 45.0
    ai_min_interval_seconds: float = 20.0  # at most one LLM call per this many seconds

    # --- Analysis ---
    current_window_seconds: int = 60  # "current value" = mean over this window
    rolling_window_minutes: int = 10  # correlation / incident-count window
    traffic_threshold_pct: float = 30.0
    transit_threshold_pct: float = 50.0
    incident_threshold_pct: float = 40.0
    incident_min_count: int = 3  # need at least this many reports before calling a spike
    # Reports are re-checked for 225 blocks × 4 report types every few seconds, so a strict
    # significance level is needed to avoid chance false alarms (multiple comparisons).
    incident_p_value: float = 0.001
    heavy_rain_mm_h: float = 7.6  # WMO/AMS "heavy rain" rate
    moderate_rain_mm_h: float = 2.5
    aqi_threshold: float = 150.0  # US AQI "Unhealthy"
    aqi_threshold_pct: float = 25.0
    water_level_threshold_cm: float = 15.0  # standing water at street sensors
    robust_z_threshold: float = 3.0

    # --- Feed freshness (multiples of the feed's expected interval) ---
    delayed_after_intervals: float = 3.0
    stale_after_intervals: float = 8.0
    unavailable_after_minutes: float = 10.0

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.city_timezone)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
