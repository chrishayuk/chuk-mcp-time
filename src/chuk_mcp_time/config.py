"""Configuration for the time MCP server."""

from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TimeServerConfig(BaseSettings):
    """Configuration for the time MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="TIME_SERVER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # NTP server configuration
    ntp_servers: Annotated[
        list[str],
        Field(
            description="List of NTP servers to query for time consensus",
            default=[
                "time.cloudflare.com",
                "time.google.com",
                "time.apple.com",
                "0.pool.ntp.org",
                "1.pool.ntp.org",
                "2.pool.ntp.org",
                "3.pool.ntp.org",
            ],
        ),
    ]

    # NTP client configuration
    ntp_timeout: Annotated[
        float,
        Field(
            description="Timeout for NTP queries in seconds",
            default=2.0,
            ge=0.5,
            le=10.0,
        ),
    ]

    # Consensus engine configuration
    max_outlier_deviation_ms: Annotated[
        float,
        Field(
            description="Maximum deviation from median to reject as outlier (milliseconds)",
            default=5000.0,
            ge=100.0,
            le=60000.0,
        ),
    ]

    min_sources: Annotated[
        int,
        Field(
            description="Minimum number of sources required for consensus",
            default=3,
            ge=1,
            le=10,
        ),
    ]

    max_disagreement_ms: Annotated[
        float,
        Field(
            description="Maximum disagreement before warning (milliseconds)",
            default=250.0,
            ge=10.0,
            le=5000.0,
        ),
    ]

    # Accuracy mode configuration
    fast_mode_server_count: Annotated[
        int,
        Field(
            description="Number of servers to query in fast mode",
            default=4,
            ge=2,
            le=10,
        ),
    ]


def load_config() -> TimeServerConfig:
    """Load configuration from environment variables and .env file.

    Returns:
        TimeServerConfig instance
    """
    return TimeServerConfig()


# Global config instance (lazily loaded)
_config: TimeServerConfig | None = None


def get_config() -> TimeServerConfig:
    """Get the global configuration instance.

    Returns:
        TimeServerConfig instance
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config
