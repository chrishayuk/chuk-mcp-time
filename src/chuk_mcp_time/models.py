"""Pydantic models for the time MCP server."""

from enum import Enum

from pydantic import BaseModel, Field


class AccuracyMode(str, Enum):
    """Accuracy mode for time queries."""

    FAST = "fast"  # Fewer sources, lower latency
    ACCURATE = "accurate"  # More sources, higher accuracy


class ConsensusMethod(str, Enum):
    """Consensus calculation method."""

    MEDIAN_WITH_OUTLIER_REJECTION = "median_with_outlier_rejection"
    SYSTEM_FALLBACK = "system_fallback"


class ClockStatus(str, Enum):
    """System clock status relative to trusted time."""

    OK = "ok"  # Delta < 100ms
    DRIFT = "drift"  # Delta 100-1000ms
    ERROR = "error"  # Delta > 1000ms


class NTPError(str, Enum):
    """NTP error types."""

    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"


class NTPResponse(BaseModel):
    """Response from an NTP server."""

    server: str = Field(description="NTP server hostname or IP")
    timestamp: float = Field(description="Unix timestamp from NTP server")
    rtt_ms: float = Field(description="Round-trip time in milliseconds")
    stratum: int = Field(description="NTP stratum (quality indicator, 0-16)")
    success: bool = Field(description="Whether the query was successful")
    error: str | None = Field(None, description="Error message if query failed")
    error_type: NTPError | None = Field(None, description="Type of error if query failed")


class SourceSample(BaseModel):
    """Sample from a single time source."""

    server: str = Field(description="NTP server hostname")
    success: bool = Field(description="Whether the query succeeded")
    timestamp: float | None = Field(None, description="Unix timestamp if successful")
    rtt_ms: float | None = Field(None, description="Round-trip time in milliseconds")
    stratum: int | None = Field(None, description="NTP stratum (0-16)")
    error: str | None = Field(None, description="Error message if failed")


class TimeConsensus(BaseModel):
    """Result of time consensus calculation."""

    # Consensus time
    timestamp: float = Field(description="Unix timestamp (seconds)")
    iso8601_time: str = Field(description="ISO 8601 formatted UTC time")
    epoch_ms: int = Field(description="Unix timestamp in milliseconds")

    # Consensus metadata
    sources_used: int = Field(description="Number of sources used in consensus")
    total_sources: int = Field(description="Total number of sources queried")
    consensus_method: ConsensusMethod = Field(description="Algorithm used for consensus")
    estimated_error_ms: float = Field(description="Estimated error in milliseconds")

    # Source details
    source_samples: list[SourceSample] = Field(description="Raw data from each source")
    warnings: list[str] = Field(default_factory=list, description="Warnings and issues")

    # System clock comparison
    system_time: str = Field(description="System clock time (ISO 8601)")
    system_delta_ms: float = Field(
        description="Difference between consensus and system time (positive = system ahead)"
    )


class TimeResponse(BaseModel):
    """Response for get_time_utc tool."""

    iso8601_time: str = Field(description="Current time in ISO 8601 format (UTC)")
    epoch_ms: int = Field(description="Unix timestamp in milliseconds")
    sources_used: int = Field(description="Number of sources used in consensus")
    total_sources: int = Field(description="Total number of sources queried")
    consensus_method: str = Field(description="Algorithm used for consensus")
    estimated_error_ms: float = Field(description="Estimated error in milliseconds")
    source_samples: list[dict[str, str | float | int | bool | None]] = Field(
        description="Raw data from each NTP server"
    )
    warnings: list[str] = Field(description="Warnings and issues")
    system_time: str = Field(description="System clock time for comparison")
    system_delta_ms: float = Field(
        description="Difference between consensus and system time (ms, positive = system ahead)"
    )
    query_duration_ms: float = Field(
        description="Time taken to query NTP servers and compute consensus (ms)"
    )
    latency_compensated: bool = Field(
        description="Whether the timestamp was adjusted for query latency"
    )


class TimezoneResponse(TimeResponse):
    """Response for get_time_for_timezone tool."""

    timezone: str = Field(description="IANA timezone name")
    local_time: str = Field(description="Time in the requested timezone (ISO 8601)")


class ClockComparisonResponse(BaseModel):
    """Response for compare_system_clock tool."""

    system_time: str = Field(description="Current system clock time (ISO 8601, UTC)")
    trusted_time: str = Field(description="NTP consensus time (ISO 8601, UTC)")
    delta_ms: float = Field(description="Difference in milliseconds (positive = system is ahead)")
    estimated_error_ms: float = Field(description="Estimated error of the consensus time")
    status: ClockStatus = Field(description="Clock status: ok, drift, or error")
