"""Tests for server integration (simpler approach)."""

import pytest

from chuk_mcp_time.config import get_config
from chuk_mcp_time.consensus import TimeConsensusEngine
from chuk_mcp_time.models import AccuracyMode
from chuk_mcp_time.ntp_client import NTPClient


@pytest.mark.asyncio
@pytest.mark.network
async def test_full_integration_fast_mode() -> None:
    """Test full integration in fast mode (simulates what the server does)."""
    config = get_config()
    ntp_client = NTPClient(timeout=config.ntp_timeout)
    consensus_engine = TimeConsensusEngine(
        max_outlier_deviation_ms=config.max_outlier_deviation_ms,
        min_sources=config.min_sources,
        max_disagreement_ms=config.max_disagreement_ms,
    )

    # Query servers (fast mode)
    servers = config.ntp_servers[: config.fast_mode_server_count]
    responses = await ntp_client.query_multiple_servers(servers)

    # Compute consensus
    consensus = consensus_engine.compute_consensus(responses)

    # Verify results
    assert consensus.iso8601_time
    assert consensus.epoch_ms > 0
    assert consensus.sources_used >= 1
    assert consensus.total_sources == len(servers)
    assert consensus.estimated_error_ms > 0


@pytest.mark.asyncio
@pytest.mark.network
async def test_full_integration_accurate_mode() -> None:
    """Test full integration in accurate mode."""
    config = get_config()
    ntp_client = NTPClient(timeout=config.ntp_timeout)
    consensus_engine = TimeConsensusEngine()

    # Query servers (accurate mode - all servers)
    servers = config.ntp_servers
    responses = await ntp_client.query_multiple_servers(servers)

    # Compute consensus
    consensus = consensus_engine.compute_consensus(responses)

    # Verify results
    assert consensus.sources_used >= 1
    assert consensus.total_sources == len(servers)
    assert len(consensus.source_samples) == len(servers)


@pytest.mark.asyncio
@pytest.mark.network
async def test_timezone_conversion_integration() -> None:
    """Test timezone conversion (simulates get_time_for_timezone)."""
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    config = get_config()
    ntp_client = NTPClient(timeout=config.ntp_timeout)
    consensus_engine = TimeConsensusEngine()

    # Get consensus
    responses = await ntp_client.query_multiple_servers(config.ntp_servers[:4])
    consensus = consensus_engine.compute_consensus(responses)

    # Apply latency compensation
    query_duration = 0.15  # Simulate 150ms query
    compensated_timestamp = consensus.timestamp + query_duration

    # Convert to timezone
    utc_dt = datetime.fromtimestamp(compensated_timestamp, tz=UTC)
    ny_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))

    assert ny_dt.tzinfo is not None
    assert (
        "America/New_York" in str(ny_dt.tzinfo)
        or "EST" in str(ny_dt.tzinfo)
        or "EDT" in str(ny_dt.tzinfo)
    )


@pytest.mark.asyncio
async def test_clock_comparison_logic() -> None:
    """Test clock comparison logic."""

    from chuk_mcp_time.models import ClockStatus

    # Simulate different deltas
    test_cases = [
        (50.0, ClockStatus.OK),  # 50ms = OK
        (150.0, ClockStatus.DRIFT),  # 150ms = DRIFT
        (1500.0, ClockStatus.ERROR),  # 1500ms = ERROR
    ]

    for delta_ms, expected_status in test_cases:
        abs_delta = abs(delta_ms)
        if abs_delta < 100:
            status = ClockStatus.OK
        elif abs_delta < 1000:
            status = ClockStatus.DRIFT
        else:
            status = ClockStatus.ERROR

        assert status == expected_status


def test_server_main_exists() -> None:
    """Test that server main function exists."""
    from chuk_mcp_time.server import main

    # Just verify the function exists and is callable
    assert callable(main)


def test_main_stdio_mode() -> None:
    """Test main function in stdio mode."""
    from unittest.mock import patch

    with patch("chuk_mcp_time.server.run") as mock_run:
        with patch("sys.argv", ["chuk-mcp-time"]):
            from chuk_mcp_time.server import main

            main()
            mock_run.assert_called_once_with(transport="stdio")


def test_main_http_mode() -> None:
    """Test main function in http mode."""
    from unittest.mock import patch

    with patch("chuk_mcp_time.server.run") as mock_run:
        with patch("sys.argv", ["chuk-mcp-time", "http"]):
            from chuk_mcp_time.server import main

            main()
            mock_run.assert_called_once_with(transport="http")


def test_main_http_mode_with_flag() -> None:
    """Test main function with --http flag."""
    from unittest.mock import patch

    with patch("chuk_mcp_time.server.run") as mock_run:
        with patch("sys.argv", ["chuk-mcp-time", "--http"]):
            from chuk_mcp_time.server import main

            main()
            mock_run.assert_called_once_with(transport="http")


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_time_utc_fast_mode() -> None:
    """Test get_time_utc tool function in fast mode."""
    from chuk_mcp_time.server import get_time_utc

    response = await get_time_utc(mode=AccuracyMode.FAST, compensate_latency=True)

    assert response.iso8601_time
    assert response.epoch_ms > 0
    assert response.sources_used >= 1
    assert response.consensus_method in [
        "median_with_outlier_rejection",
        "median",
        "single_source",
        "fallback",
    ]
    assert response.estimated_error_ms > 0
    assert response.query_duration_ms > 0
    assert response.latency_compensated is True
    assert isinstance(response.source_samples, list)


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_time_utc_accurate_mode() -> None:
    """Test get_time_utc tool function in accurate mode."""
    from chuk_mcp_time.server import get_time_utc

    response = await get_time_utc(mode=AccuracyMode.ACCURATE, compensate_latency=True)

    assert response.iso8601_time
    assert response.epoch_ms > 0
    assert response.sources_used >= 1
    assert response.latency_compensated is True


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_time_utc_no_compensation() -> None:
    """Test get_time_utc without latency compensation."""
    from chuk_mcp_time.server import get_time_utc

    response = await get_time_utc(mode=AccuracyMode.FAST, compensate_latency=False)

    assert response.iso8601_time
    assert response.latency_compensated is False


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_time_for_timezone_valid() -> None:
    """Test get_time_for_timezone with valid timezone."""
    from chuk_mcp_time.server import get_time_for_timezone

    response = await get_time_for_timezone(
        timezone_name="America/New_York",
        mode=AccuracyMode.FAST,
        compensate_latency=True,
    )

    assert response.timezone == "America/New_York"
    assert response.local_time
    assert "ERROR" not in response.local_time
    assert response.iso8601_time  # Should have UTC time too


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_time_for_timezone_invalid() -> None:
    """Test get_time_for_timezone with invalid timezone."""
    from chuk_mcp_time.server import get_time_for_timezone

    response = await get_time_for_timezone(
        timezone_name="Invalid/Timezone",
        mode=AccuracyMode.FAST,
        compensate_latency=True,
    )

    assert response.timezone == "Invalid/Timezone"
    assert "ERROR" in response.local_time
    assert any("Failed to convert to timezone" in w for w in response.warnings)


@pytest.mark.asyncio
@pytest.mark.network
async def test_compare_system_clock_fast_mode() -> None:
    """Test compare_system_clock function."""
    from chuk_mcp_time.models import ClockStatus
    from chuk_mcp_time.server import compare_system_clock

    response = await compare_system_clock(mode=AccuracyMode.FAST)

    assert response.system_time
    assert response.trusted_time
    assert isinstance(response.delta_ms, float)
    assert response.estimated_error_ms > 0
    assert response.status in [ClockStatus.OK, ClockStatus.DRIFT, ClockStatus.ERROR]


@pytest.mark.asyncio
@pytest.mark.network
async def test_compare_system_clock_accurate_mode() -> None:
    """Test compare_system_clock in accurate mode."""
    from chuk_mcp_time.server import compare_system_clock

    response = await compare_system_clock(mode=AccuracyMode.ACCURATE)

    assert response.system_time
    assert response.trusted_time
    assert isinstance(response.delta_ms, float)


@pytest.mark.asyncio
async def test_compare_system_clock_status_logic() -> None:
    """Test that compare_system_clock correctly categorizes clock status."""
    from unittest.mock import AsyncMock, patch

    from chuk_mcp_time.models import ClockStatus, TimeResponse
    from chuk_mcp_time.server import compare_system_clock

    # Test DRIFT status (delta between 100-1000ms)
    mock_response_drift = TimeResponse(
        iso8601_time="2025-11-28T10:00:00.000000+00:00",
        epoch_ms=1700000000000,
        sources_used=4,
        total_sources=4,
        consensus_method="median",
        estimated_error_ms=10.0,
        source_samples=[],
        warnings=[],
        system_time="2025-11-28T10:00:00.500000+00:00",
        system_delta_ms=500.0,  # DRIFT range
        query_duration_ms=10.0,
        latency_compensated=True,
    )

    with patch("chuk_mcp_time.server.get_time_utc", new_callable=AsyncMock) as mock_get_time:
        mock_get_time.return_value = mock_response_drift
        response = await compare_system_clock(mode=AccuracyMode.FAST)
        assert response.status == ClockStatus.DRIFT

    # Test ERROR status (delta > 1000ms)
    mock_response_error = TimeResponse(
        iso8601_time="2025-11-28T10:00:00.000000+00:00",
        epoch_ms=1700000000000,
        sources_used=4,
        total_sources=4,
        consensus_method="median",
        estimated_error_ms=10.0,
        source_samples=[],
        warnings=[],
        system_time="2025-11-28T10:00:02.000000+00:00",
        system_delta_ms=2000.0,  # ERROR range
        query_duration_ms=10.0,
        latency_compensated=True,
    )

    with patch("chuk_mcp_time.server.get_time_utc", new_callable=AsyncMock) as mock_get_time:
        mock_get_time.return_value = mock_response_error
        response = await compare_system_clock(mode=AccuracyMode.FAST)
        assert response.status == ClockStatus.ERROR


@pytest.mark.asyncio
async def test_get_time_utc_latency_compensation_warnings() -> None:
    """Test that latency compensation adds warnings for slow queries."""
    from unittest.mock import AsyncMock, patch

    from chuk_mcp_time.models import ConsensusMethod, TimeConsensus
    from chuk_mcp_time.server import get_time_utc

    # Mock consensus that would trigger latency warning (>100ms)
    mock_consensus = TimeConsensus(
        timestamp=1700000000.0,
        iso8601_time="2025-11-28T10:00:00.000000+00:00",
        epoch_ms=1700000000000,
        sources_used=4,
        total_sources=4,
        consensus_method=ConsensusMethod.MEDIAN_WITH_OUTLIER_REJECTION,
        estimated_error_ms=10.0,
        source_samples=[],
        warnings=[],
        system_time="2025-11-28T10:00:00.000000+00:00",
        system_delta_ms=0.0,
    )

    # Mock slow query by patching time.time to simulate 150ms query
    original_time = __import__("time").time
    call_count = [0]

    def mock_time():
        call_count[0] += 1
        if call_count[0] == 1:
            return original_time()  # Start time
        else:
            return original_time() + 0.15  # End time (150ms later)

    with patch("chuk_mcp_time.server._consensus_engine.compute_consensus") as mock_compute:
        with patch(
            "chuk_mcp_time.server._ntp_client.query_multiple_servers", new_callable=AsyncMock
        ) as mock_query:
            with patch("chuk_mcp_time.server.time_module.time", side_effect=mock_time):
                mock_compute.return_value = mock_consensus
                mock_query.return_value = []

                response = await get_time_utc(mode=AccuracyMode.FAST, compensate_latency=True)

                # Should have added latency compensation warning
                assert any("latency compensation" in w.lower() for w in response.warnings)


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_local_time() -> None:
    """Test get_local_time tool function."""
    from chuk_mcp_time.server import get_local_time

    response = await get_local_time(
        timezone="America/New_York",
        mode=AccuracyMode.FAST,
        compensate_latency=True,
    )

    assert response.local_datetime
    assert response.timezone == "America/New_York"
    assert isinstance(response.utc_offset_seconds, int)
    assert isinstance(response.is_dst, bool)
    assert response.abbreviation in ["EST", "EDT"]
    assert response.source_utc
    assert response.tzdata_version
    assert response.estimated_error_ms > 0


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_local_time_utc() -> None:
    """Test get_local_time with UTC timezone."""
    from chuk_mcp_time.server import get_local_time

    response = await get_local_time(timezone="UTC", mode=AccuracyMode.FAST)

    assert response.timezone == "UTC"
    assert response.utc_offset_seconds == 0
    assert response.is_dst is False
    assert response.abbreviation == "UTC"


@pytest.mark.asyncio
async def test_convert_time() -> None:
    """Test convert_time tool function."""
    from chuk_mcp_time.server import convert_time

    response = await convert_time(
        datetime_str="2025-06-15T14:00:00",
        from_timezone="America/New_York",
        to_timezone="Europe/London",
    )

    assert response.from_timezone == "America/New_York"
    assert response.to_timezone == "Europe/London"
    assert response.from_datetime
    assert response.to_datetime
    assert response.from_utc_offset_seconds == -14400  # EDT
    assert response.to_utc_offset_seconds == 3600  # BST
    assert response.offset_difference_seconds == 18000  # 5 hours
    assert "ahead" in response.explanation or "behind" in response.explanation


@pytest.mark.asyncio
async def test_convert_time_winter() -> None:
    """Test convert_time during winter (standard time)."""
    from chuk_mcp_time.server import convert_time

    response = await convert_time(
        datetime_str="2025-01-15T14:00:00",
        from_timezone="America/New_York",
        to_timezone="Europe/London",
    )

    assert response.from_utc_offset_seconds == -18000  # EST
    assert response.to_utc_offset_seconds == 0  # GMT
    assert response.offset_difference_seconds == 18000


@pytest.mark.asyncio
async def test_convert_time_same_timezone() -> None:
    """Test convert_time within same timezone."""
    from chuk_mcp_time.server import convert_time

    response = await convert_time(
        datetime_str="2025-06-15T14:00:00",
        from_timezone="America/New_York",
        to_timezone="America/New_York",
    )

    assert response.from_utc_offset_seconds == response.to_utc_offset_seconds
    assert response.offset_difference_seconds == 0
    assert "same UTC offset" in response.explanation


@pytest.mark.asyncio
async def test_list_timezones() -> None:
    """Test list_timezones tool function."""
    from chuk_mcp_time.server import list_timezones

    response = await list_timezones()

    assert response.total_count > 100
    assert len(response.timezones) > 100
    assert response.tzdata_version

    # Check first timezone has expected structure
    tz = response.timezones[0]
    assert tz.id
    assert isinstance(tz.country_code, str) or tz.country_code is None
    assert isinstance(tz.comment, str) or tz.comment is None
    assert isinstance(tz.example_city, str) or tz.example_city is None


@pytest.mark.asyncio
async def test_list_timezones_with_search() -> None:
    """Test list_timezones with search filter."""
    from chuk_mcp_time.server import list_timezones

    response = await list_timezones(search="New_York")

    assert response.total_count >= 1
    assert any(tz.id == "America/New_York" for tz in response.timezones)


@pytest.mark.asyncio
async def test_list_timezones_search_case_insensitive() -> None:
    """Test that list_timezones search is case-insensitive."""
    from chuk_mcp_time.server import list_timezones

    response_lower = await list_timezones(search="london")
    response_upper = await list_timezones(search="LONDON")

    assert response_lower.total_count == response_upper.total_count
    assert response_lower.total_count >= 1


@pytest.mark.asyncio
async def test_list_timezones_no_results() -> None:
    """Test list_timezones with search that returns no results."""
    from chuk_mcp_time.server import list_timezones

    response = await list_timezones(search="NonExistentTimezone12345")

    assert response.total_count == 0
    assert len(response.timezones) == 0


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_timezone_info() -> None:
    """Test get_timezone_info tool function."""
    from chuk_mcp_time.server import get_timezone_info

    response = await get_timezone_info(timezone="America/New_York", mode=AccuracyMode.FAST)

    assert response.timezone == "America/New_York"
    assert isinstance(response.current_offset_seconds, int)
    assert isinstance(response.current_is_dst, bool)
    assert response.current_abbreviation in ["EST", "EDT"]
    assert isinstance(response.transitions, list)
    assert response.tzdata_version


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_timezone_info_with_transitions() -> None:
    """Test that get_timezone_info returns DST transitions."""
    from chuk_mcp_time.server import get_timezone_info

    response = await get_timezone_info(timezone="America/New_York", mode=AccuracyMode.FAST)

    # New York has DST transitions
    assert len(response.transitions) >= 2

    # Check transition structure
    for transition in response.transitions:
        assert transition.from_datetime
        assert isinstance(transition.utc_offset_seconds, int)
        assert isinstance(transition.is_dst, bool)
        assert transition.abbreviation


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_timezone_info_no_dst() -> None:
    """Test get_timezone_info for timezone without DST."""
    from chuk_mcp_time.server import get_timezone_info

    # Phoenix doesn't observe DST
    response = await get_timezone_info(timezone="America/Phoenix", mode=AccuracyMode.FAST)

    assert response.timezone == "America/Phoenix"
    assert response.current_is_dst is False
    # Should have very few or no transitions
    assert len(response.transitions) <= 1
