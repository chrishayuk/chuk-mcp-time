"""Tests for timezone utilities."""

from datetime import UTC, datetime

from chuk_mcp_time.timezone_utils import (
    convert_datetime_between_timezones,
    find_timezone_transitions,
    get_timezone_info_at_datetime,
    get_tzdata_version,
    list_all_timezones,
)


def test_get_tzdata_version() -> None:
    """Test getting tzdata version."""
    version = get_tzdata_version()
    assert isinstance(version, str)
    assert len(version) > 0
    # Should be either a version string or "system" or "unknown"
    assert version in ["system", "unknown"] or version[0].isdigit()


def test_get_timezone_info_at_datetime() -> None:
    """Test getting timezone info at a specific datetime."""
    # Test with EST (winter time in New York)
    dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
    info = get_timezone_info_at_datetime("America/New_York", dt)

    assert "utc_offset_seconds" in info
    assert "is_dst" in info
    assert "abbreviation" in info

    # EST is UTC-5, so -18000 seconds
    assert info["utc_offset_seconds"] == -18000
    assert info["is_dst"] is False
    assert info["abbreviation"] == "EST"


def test_get_timezone_info_at_datetime_dst() -> None:
    """Test getting timezone info during DST."""
    # Test with EDT (summer time in New York)
    dt = datetime(2025, 7, 15, 12, 0, 0, tzinfo=UTC)
    info = get_timezone_info_at_datetime("America/New_York", dt)

    # EDT is UTC-4, so -14400 seconds
    assert info["utc_offset_seconds"] == -14400
    assert info["is_dst"] is True
    assert info["abbreviation"] == "EDT"


def test_get_timezone_info_utc() -> None:
    """Test getting timezone info for UTC."""
    dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
    info = get_timezone_info_at_datetime("UTC", dt)

    assert info["utc_offset_seconds"] == 0
    assert info["is_dst"] is False
    assert info["abbreviation"] == "UTC"


def test_find_timezone_transitions() -> None:
    """Test finding timezone transitions."""
    # Find transitions in America/New_York for 1 year
    start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    transitions = find_timezone_transitions("America/New_York", start, end)

    # Should find at least 2 transitions (spring forward, fall back)
    assert len(transitions) >= 2

    # Check structure of transitions
    for t in transitions:
        assert "from_datetime" in t
        assert "utc_offset_seconds" in t
        assert "is_dst" in t
        assert "abbreviation" in t


def test_find_timezone_transitions_no_dst() -> None:
    """Test finding transitions for timezone without DST."""
    # Arizona doesn't observe DST
    start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    transitions = find_timezone_transitions("America/Phoenix", start, end)

    # Should find no transitions or very few
    assert len(transitions) <= 1


def test_list_all_timezones() -> None:
    """Test listing all timezones."""
    timezones = list_all_timezones()

    # Should return many timezones
    assert len(timezones) > 100

    # Check structure
    for tz in timezones[:5]:  # Just check first 5
        assert "id" in tz
        assert "country_code" in tz or tz["country_code"] is None
        assert "comment" in tz or tz["comment"] is None
        assert "example_city" in tz or tz["example_city"] is None


def test_list_all_timezones_search() -> None:
    """Test listing timezones with search filter."""
    timezones = list_all_timezones(search="New_York")

    # Should find America/New_York
    assert len(timezones) >= 1
    assert any(tz["id"] == "America/New_York" for tz in timezones)


def test_list_all_timezones_search_case_insensitive() -> None:
    """Test that search is case-insensitive."""
    timezones_lower = list_all_timezones(search="london")
    timezones_upper = list_all_timezones(search="LONDON")

    assert len(timezones_lower) == len(timezones_upper)
    assert len(timezones_lower) >= 1


def test_list_all_timezones_search_no_results() -> None:
    """Test searching for non-existent timezone."""
    timezones = list_all_timezones(search="NonExistentTimezone12345")

    assert len(timezones) == 0


def test_convert_datetime_between_timezones() -> None:
    """Test converting datetime between timezones."""
    result = convert_datetime_between_timezones(
        "2025-06-15T14:00:00", "America/New_York", "Europe/London"
    )

    assert result["from_timezone"] == "America/New_York"
    assert result["to_timezone"] == "Europe/London"
    assert "from_datetime" in result
    assert "to_datetime" in result
    assert "from_utc_offset_seconds" in result
    assert "to_utc_offset_seconds" in result
    assert "offset_difference_seconds" in result
    assert "explanation" in result

    # Check offset values are reasonable
    # NYC in June is EDT (UTC-4), London in June is BST (UTC+1)
    assert result["from_utc_offset_seconds"] == -14400  # -4 hours
    assert result["to_utc_offset_seconds"] == 3600  # +1 hour
    assert result["offset_difference_seconds"] == 18000  # 5 hour difference

    # Explanation should be present and meaningful
    assert "ahead" in result["explanation"] or "behind" in result["explanation"]


def test_convert_datetime_winter() -> None:
    """Test converting datetime in winter (standard time)."""
    result = convert_datetime_between_timezones(
        "2025-01-15T14:00:00", "America/New_York", "Europe/London"
    )

    # NYC in January is EST (UTC-5), London in January is GMT (UTC+0)
    assert result["from_utc_offset_seconds"] == -18000  # -5 hours
    assert result["to_utc_offset_seconds"] == 0  # UTC+0
    assert result["offset_difference_seconds"] == 18000  # 5 hour difference


def test_convert_datetime_same_timezone() -> None:
    """Test converting within same timezone."""
    result = convert_datetime_between_timezones(
        "2025-06-15T14:00:00", "America/New_York", "America/New_York"
    )

    assert result["from_utc_offset_seconds"] == result["to_utc_offset_seconds"]
    assert result["offset_difference_seconds"] == 0
    assert "same UTC offset" in result["explanation"]


def test_convert_datetime_to_utc() -> None:
    """Test converting to UTC."""
    result = convert_datetime_between_timezones("2025-06-15T14:00:00", "America/New_York", "UTC")

    assert result["to_utc_offset_seconds"] == 0
    assert result["from_utc_offset_seconds"] == -14400  # EDT


def test_convert_datetime_across_date_line() -> None:
    """Test converting across the international date line."""
    result = convert_datetime_between_timezones(
        "2025-06-15T23:00:00", "America/Los_Angeles", "Asia/Tokyo"
    )

    # LA to Tokyo crosses date line, should result in next day in Tokyo
    from_dt = result["from_datetime"]
    to_dt = result["to_datetime"]

    # Parse the dates to verify day change
    assert "2025-06-15" in from_dt
    assert "2025-06-16" in to_dt  # Should be next day in Tokyo
