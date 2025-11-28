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
    TimeResponse,
    TimezoneResponse,
)
from chuk_mcp_time.ntp_client import NTPClient

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
