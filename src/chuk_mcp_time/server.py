"""MCP server for high-accuracy time using NTP consensus."""

import logging
import sys
import time as time_module
from datetime import UTC, datetime

from chuk_mcp_server import run, tool

from chuk_mcp_time.config import get_config
from chuk_mcp_time.consensus import TimeConsensusEngine
from chuk_mcp_time.models import (
    AccuracyMode,
    ClockComparisonResponse,
    ClockStatus,
    ListTimezonesResponse,
    LocalTimeResponse,
    TimeResponse,
    TimezoneConversionResponse,
    TimezoneDetailResponse,
    TimezoneInfo,
    TimezoneResponse,
    TimezoneTransition,
)
from chuk_mcp_time.ntp_client import NTPClient
from chuk_mcp_time.timezone_utils import (
    convert_datetime_between_timezones,
    find_timezone_transitions,
    get_timezone_info_at_datetime,
    get_tzdata_version,
    list_all_timezones,
)

# Initialize components
_config = get_config()
_ntp_client = NTPClient(timeout=_config.ntp_timeout)
_consensus_engine = TimeConsensusEngine(
    max_outlier_deviation_ms=_config.max_outlier_deviation_ms,
    min_sources=_config.min_sources,
    max_disagreement_ms=_config.max_disagreement_ms,
)


@tool  # type: ignore[arg-type]
async def get_time_utc(
    mode: AccuracyMode = AccuracyMode.FAST,
    compensate_latency: bool = True,
) -> TimeResponse:
    """Get current UTC time with high accuracy using NTP consensus.

    Queries multiple NTP servers, removes outliers, and computes a consensus time
    that is independent of the system clock. Returns detailed information about
    all sources, consensus method, and estimated error.

    By default, the returned timestamp is compensated for the time it took to
    query NTP servers and compute consensus. This means the timestamp represents
    the time when the response is returned, not when NTP servers were queried.

    Args:
        mode: Accuracy mode - "fast" uses 3-4 servers, "accurate" uses 7 servers
        compensate_latency: If True, add query duration to timestamp (default: True)

    Returns:
        TimeResponse with consensus time and metadata
    """
    # Record start time for latency compensation
    query_start = time_module.time()

    # Select servers based on mode
    if mode == AccuracyMode.FAST:
        servers = _config.ntp_servers[: _config.fast_mode_server_count]
    else:
        servers = _config.ntp_servers

    # Query NTP servers asynchronously
    responses = await _ntp_client.query_multiple_servers(servers)

    # Compute consensus
    consensus = _consensus_engine.compute_consensus(responses)

    # Calculate query duration
    query_duration = time_module.time() - query_start
    query_duration_ms = query_duration * 1000

    # Apply latency compensation if requested
    if compensate_latency:
        # Add query duration to consensus timestamp
        compensated_timestamp = consensus.timestamp + query_duration
        compensated_epoch_ms = int(compensated_timestamp * 1000)
        compensated_iso8601 = datetime.fromtimestamp(compensated_timestamp, tz=UTC).isoformat()

        # Add note to warnings if compensation is significant
        warnings = list(consensus.warnings)
        if query_duration_ms > 100:
            warnings.append(f"Applied +{query_duration_ms:.1f}ms latency compensation to timestamp")

        # Update estimated error to include query duration uncertainty
        # The longer the query took, the more uncertainty we add
        adjusted_error = consensus.estimated_error_ms + (query_duration_ms * 0.1)

        # Recalculate system delta with compensated timestamp
        # System delta should reflect the compensated timestamp, not the original
        current_system_time = time_module.time()
        system_delta_ms = (current_system_time - compensated_timestamp) * 1000

        iso8601_time = compensated_iso8601
        epoch_ms = compensated_epoch_ms
        estimated_error_ms = adjusted_error
    else:
        iso8601_time = consensus.iso8601_time
        epoch_ms = consensus.epoch_ms
        estimated_error_ms = consensus.estimated_error_ms
        warnings = consensus.warnings
        system_delta_ms = consensus.system_delta_ms

    # Convert source samples to dict for JSON serialization
    source_samples = [s.model_dump() for s in consensus.source_samples]

    return TimeResponse(
        iso8601_time=iso8601_time,
        epoch_ms=epoch_ms,
        sources_used=consensus.sources_used,
        total_sources=consensus.total_sources,
        consensus_method=consensus.consensus_method.value,
        estimated_error_ms=estimated_error_ms,
        source_samples=source_samples,
        warnings=warnings,
        system_time=consensus.system_time,
        system_delta_ms=system_delta_ms,
        query_duration_ms=query_duration_ms,
        latency_compensated=compensate_latency,
    )


@tool  # type: ignore[arg-type]
async def get_time_for_timezone(
    timezone_name: str,
    mode: AccuracyMode = AccuracyMode.FAST,
    compensate_latency: bool = True,
) -> TimezoneResponse:
    """Get current time for a specific timezone with high accuracy.

    Queries multiple NTP servers for accurate UTC time, then converts to the
    requested timezone. Includes all consensus metadata and source details.

    Args:
        timezone_name: IANA timezone name (e.g., "America/New_York")
        mode: Accuracy mode - "fast" or "accurate"
        compensate_latency: If True, add query duration to timestamp (default: True)

    Returns:
        TimezoneResponse with time in specified timezone
    """
    # Get UTC consensus first
    time_response = await get_time_utc(mode=mode, compensate_latency=compensate_latency)  # type: ignore[misc]

    # Convert to requested timezone
    try:
        from zoneinfo import ZoneInfo

        utc_timestamp = time_response.epoch_ms / 1000.0
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC)
        local_dt = utc_dt.astimezone(ZoneInfo(timezone_name))
        local_time = local_dt.isoformat()

        return TimezoneResponse(
            **time_response.model_dump(),
            timezone=timezone_name,
            local_time=local_time,
        )

    except Exception as e:
        # If timezone conversion fails, add error to warnings
        warnings = list(time_response.warnings)
        warnings.append(f"Failed to convert to timezone {timezone_name}: {e}")

        # Get base data but exclude warnings since we're overriding it
        base_data = time_response.model_dump(exclude={"warnings"})

        return TimezoneResponse(
            **base_data,
            timezone=timezone_name,
            local_time=f"ERROR: {e}",
            warnings=warnings,
        )


@tool  # type: ignore[arg-type]
async def compare_system_clock(
    mode: AccuracyMode = AccuracyMode.FAST,
) -> ClockComparisonResponse:
    """Compare system clock against trusted NTP time sources.

    Useful for detecting system clock drift or misconfiguration. Queries NTP
    servers and reports the difference between system time and consensus time.

    Args:
        mode: Accuracy mode - "fast" or "accurate"

    Returns:
        ClockComparisonResponse with comparison data
    """
    time_response = await get_time_utc(mode=mode)  # type: ignore[misc]

    # Determine status based on delta
    abs_delta = abs(time_response.system_delta_ms)
    if abs_delta < 100:
        status = ClockStatus.OK
    elif abs_delta < 1000:
        status = ClockStatus.DRIFT
    else:
        status = ClockStatus.ERROR

    return ClockComparisonResponse(
        system_time=time_response.system_time,
        trusted_time=time_response.iso8601_time,
        delta_ms=time_response.system_delta_ms,
        estimated_error_ms=time_response.estimated_error_ms,
        status=status,
    )


@tool  # type: ignore[arg-type]
async def get_local_time(
    timezone: str,
    mode: AccuracyMode = AccuracyMode.FAST,
    compensate_latency: bool = True,
) -> LocalTimeResponse:
    """Get current time for a specific IANA timezone with high accuracy.

    Uses NTP consensus for accurate UTC time, then converts to the requested
    timezone using IANA tzdata. This provides authoritative local time independent
    of system clock accuracy.

    Args:
        timezone: IANA timezone identifier (e.g., "America/New_York", "Europe/London")
        mode: Accuracy mode - "fast" or "accurate"
        compensate_latency: If True, add query duration to timestamp (default: True)

    Returns:
        LocalTimeResponse with local time and timezone metadata
    """
    # Get accurate UTC time
    time_response = await get_time_utc(mode=mode, compensate_latency=compensate_latency)  # type: ignore[misc]

    # Convert to local timezone
    utc_timestamp = time_response.epoch_ms / 1000.0
    utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC)

    # Get timezone info
    tz_info = get_timezone_info_at_datetime(timezone, utc_dt)

    # Apply timezone
    from zoneinfo import ZoneInfo

    local_dt = utc_dt.astimezone(ZoneInfo(timezone))

    return LocalTimeResponse(
        local_datetime=local_dt.isoformat(),
        timezone=timezone,
        utc_offset_seconds=tz_info.utc_offset_seconds,
        is_dst=tz_info.is_dst,
        abbreviation=tz_info.abbreviation,
        source_utc=time_response.iso8601_time,
        tzdata_version=get_tzdata_version(),
        estimated_error_ms=time_response.estimated_error_ms,
    )


@tool  # type: ignore[arg-type]
async def convert_time(
    datetime_str: str,
    from_timezone: str,
    to_timezone: str,
) -> TimezoneConversionResponse:
    """Convert a datetime from one timezone to another using IANA rules.

    Performs timezone conversion independent of system clock. Uses IANA tzdata
    to handle all DST transitions, historical changes, and political boundaries.

    Args:
        datetime_str: ISO 8601 datetime string (naive, will be interpreted in from_timezone)
        from_timezone: Source IANA timezone identifier
        to_timezone: Target IANA timezone identifier

    Returns:
        TimezoneConversionResponse with conversion details and explanation
    """
    result = convert_datetime_between_timezones(datetime_str, from_timezone, to_timezone)

    return TimezoneConversionResponse(
        from_timezone=result.from_timezone,
        from_datetime=result.from_datetime.isoformat(),
        from_utc_offset_seconds=result.from_utc_offset_seconds,
        to_timezone=result.to_timezone,
        to_datetime=result.to_datetime.isoformat(),
        to_utc_offset_seconds=result.to_utc_offset_seconds,
        offset_difference_seconds=result.offset_difference_seconds,
        explanation=result.explanation,
    )


@tool  # type: ignore[arg-type]
async def list_timezones(
    country_code: str | None = None,
    search: str | None = None,
) -> ListTimezonesResponse:
    """List available IANA timezones with optional filtering.

    Returns all valid IANA timezone identifiers. Helps discover correct timezone
    names and prevents hallucination of invalid timezones.

    Args:
        country_code: Optional ISO 3166 country code filter (e.g., "US", "GB", "FR")
        search: Optional substring search filter (case-insensitive)

    Returns:
        ListTimezonesResponse with list of timezones and metadata
    """
    timezones_data = list_all_timezones(country_code=country_code, search=search)

    timezones = [
        TimezoneInfo(
            id=tz.id,
            country_code=tz.country_code,
            comment=tz.comment,
            example_city=tz.example_city,
        )
        for tz in timezones_data
    ]

    return ListTimezonesResponse(
        timezones=timezones,
        total_count=len(timezones),
        tzdata_version=get_tzdata_version(),
    )


@tool  # type: ignore[arg-type]
async def get_timezone_info(
    timezone: str,
    mode: AccuracyMode = AccuracyMode.FAST,
) -> TimezoneDetailResponse:
    """Get detailed information about a timezone including upcoming transitions.

    Provides comprehensive timezone metadata including current offset, DST status,
    and upcoming transitions (e.g., DST changes). Useful for planning and
    understanding timezone behavior.

    Args:
        timezone: IANA timezone identifier
        mode: Accuracy mode for getting current time - "fast" or "accurate"

    Returns:
        TimezoneDetailResponse with current info and transition schedule
    """
    # Get accurate current time
    time_response = await get_time_utc(mode=mode)  # type: ignore[misc]
    utc_now = datetime.fromtimestamp(time_response.epoch_ms / 1000.0, tz=UTC)

    # Get current timezone info
    current_info = get_timezone_info_at_datetime(timezone, utc_now)

    # Find transitions in next 2 years
    end_time = datetime.fromtimestamp(
        (time_response.epoch_ms / 1000.0) + (365 * 2 * 24 * 3600), tz=UTC
    )
    transitions_data = find_timezone_transitions(timezone, utc_now, end_time)

    transitions = [
        TimezoneTransition(
            from_datetime=t.from_datetime.isoformat(),
            utc_offset_seconds=t.utc_offset_seconds,
            is_dst=t.is_dst,
            abbreviation=t.abbreviation,
        )
        for t in transitions_data
    ]

    return TimezoneDetailResponse(
        timezone=timezone,
        country_code=None,  # Would need full zone1970.tab parsing
        comment=None,
        current_offset_seconds=current_info.utc_offset_seconds,
        current_is_dst=current_info.is_dst,
        current_abbreviation=current_info.abbreviation,
        transitions=transitions,
        tzdata_version=get_tzdata_version(),
    )


def main() -> None:
    """Main entry point for the server."""
    # Check if transport is specified in command line args
    # Default to stdio for MCP compatibility (Claude Desktop, mcp-cli)
    transport = "stdio"

    # Allow HTTP mode via command line
    if len(sys.argv) > 1 and sys.argv[1] in ["http", "--http"]:
        transport = "http"
        # Configure logging for HTTP mode
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s:%(name)s:%(message)s",
            stream=sys.stderr,
        )
        logging.getLogger(__name__).info("Starting Chuk MCP Time Server in HTTP mode")

    # Suppress logging in STDIO mode to avoid polluting JSON-RPC stream
    if transport == "stdio":
        logging.basicConfig(
            level=logging.WARNING,
            format="%(levelname)s:%(name)s:%(message)s",
            stream=sys.stderr,
        )
        # Set chuk_mcp_server loggers to ERROR only
        logging.getLogger("chuk_mcp_server").setLevel(logging.ERROR)
        logging.getLogger("chuk_mcp_server.core").setLevel(logging.ERROR)
        logging.getLogger("chuk_mcp_server.stdio_transport").setLevel(logging.ERROR)

    run(transport=transport)


if __name__ == "__main__":
    main()
