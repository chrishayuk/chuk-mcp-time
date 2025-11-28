"""Timezone utilities using IANA tzdata - Pydantic-native & async-first."""

from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo, available_timezones

from pydantic import BaseModel, Field


# Constants
class TzdataSource(str, Enum):
    """Source of timezone data."""

    SYSTEM = "system"
    PACKAGE = "package"
    UNKNOWN = "unknown"


class DeprecatedTimezonePrefix(str, Enum):
    """Prefixes for deprecated timezone identifiers."""

    ETC = "Etc/"


class AllowedEtcTimezone(str, Enum):
    """Allowed Etc/ timezones (not deprecated)."""

    UTC = "Etc/UTC"
    GMT = "Etc/GMT"


# Pydantic Models
class TimezoneOffsetInfo(BaseModel):
    """Timezone offset information at a specific datetime."""

    utc_offset_seconds: int = Field(description="UTC offset in seconds")
    is_dst: bool = Field(description="Whether daylight saving time is active")
    abbreviation: str = Field(description="Timezone abbreviation (e.g., EST, BST)")


class TimezoneTransitionDetail(BaseModel):
    """Details of a timezone transition."""

    from_datetime: datetime = Field(description="Datetime when transition occurs")
    utc_offset_seconds: int = Field(description="UTC offset after transition")
    is_dst: bool = Field(description="Whether DST is active after transition")
    abbreviation: str = Field(description="Timezone abbreviation after transition")


class TimezoneListEntry(BaseModel):
    """Entry in timezone list."""

    id: str = Field(description="IANA timezone identifier")
    country_code: str | None = Field(description="ISO 3166 country code", default=None)
    comment: str | None = Field(description="Additional timezone information", default=None)
    example_city: str | None = Field(description="Example city in this timezone", default=None)


class TimezoneConversion(BaseModel):
    """Result of timezone conversion."""

    from_timezone: str = Field(description="Source IANA timezone")
    from_datetime: datetime = Field(description="Source datetime with timezone")
    from_utc_offset_seconds: int = Field(description="Source UTC offset in seconds")
    to_timezone: str = Field(description="Target IANA timezone")
    to_datetime: datetime = Field(description="Target datetime with timezone")
    to_utc_offset_seconds: int = Field(description="Target UTC offset in seconds")
    offset_difference_seconds: int = Field(description="Difference between offsets")
    explanation: str = Field(description="Human-readable explanation")


# Core Functions
def get_tzdata_version() -> str:
    """Get the IANA tzdata version.

    Returns:
        Version string (e.g., "2024b"), "system", or "unknown"
    """
    try:
        import importlib.metadata

        try:
            return importlib.metadata.version("tzdata")
        except importlib.metadata.PackageNotFoundError:
            return TzdataSource.SYSTEM

    except Exception:
        return TzdataSource.UNKNOWN


def get_timezone_info_at_datetime(tz_name: str, dt: datetime) -> TimezoneOffsetInfo:
    """Get timezone information at a specific datetime.

    Args:
        tz_name: IANA timezone identifier
        dt: Datetime to query (should be timezone-aware)

    Returns:
        TimezoneOffsetInfo with offset, DST status, and abbreviation
    """
    tz = ZoneInfo(tz_name)
    local_dt = dt.astimezone(tz)

    # Get offset in seconds
    offset = local_dt.utcoffset()
    offset_seconds = int(offset.total_seconds()) if offset else 0

    # Check if DST is active
    dst = local_dt.dst()
    is_dst = bool(dst and dst.total_seconds() != 0)

    # Get abbreviation
    abbreviation = local_dt.tzname() or ""

    return TimezoneOffsetInfo(
        utc_offset_seconds=offset_seconds,
        is_dst=is_dst,
        abbreviation=abbreviation,
    )


def find_timezone_transitions(
    tz_name: str, start_dt: datetime, end_dt: datetime
) -> list[TimezoneTransitionDetail]:
    """Find timezone transitions in a date range.

    Args:
        tz_name: IANA timezone identifier
        start_dt: Start datetime (UTC)
        end_dt: End datetime (UTC)

    Returns:
        List of TimezoneTransitionDetail objects
    """
    transitions: list[TimezoneTransitionDetail] = []

    # Sample daily to detect transition windows
    current = start_dt
    prev_info: TimezoneOffsetInfo | None = None

    while current <= end_dt:
        info = get_timezone_info_at_datetime(tz_name, current)

        # Check if offset or DST status changed
        if prev_info and (
            info.utc_offset_seconds != prev_info.utc_offset_seconds
            or info.is_dst != prev_info.is_dst
        ):
            # Transition detected between prev_time and current
            # Use binary search to find exact transition time (within 1 minute)
            prev_time = current - timedelta(days=1)
            transition_time = _find_exact_transition(tz_name, prev_time, current, prev_info, info)

            transitions.append(
                TimezoneTransitionDetail(
                    from_datetime=transition_time,
                    utc_offset_seconds=info.utc_offset_seconds,
                    is_dst=info.is_dst,
                    abbreviation=info.abbreviation,
                )
            )

        prev_info = info
        current += timedelta(days=1)

    return transitions


def _find_exact_transition(
    tz_name: str,
    start: datetime,
    end: datetime,
    prev_info: TimezoneOffsetInfo,
    new_info: TimezoneOffsetInfo,
) -> datetime:
    """Binary search to find exact transition time within a window.

    Args:
        tz_name: IANA timezone identifier
        start: Start of window (before transition)
        end: End of window (after transition)
        prev_info: Timezone info before transition
        new_info: Timezone info after transition

    Returns:
        Datetime of transition (accurate to ~1 minute)
    """
    # Binary search with 1-minute precision
    while (end - start).total_seconds() > 60:
        mid = start + (end - start) / 2
        mid_info = get_timezone_info_at_datetime(tz_name, mid)

        if (
            mid_info.utc_offset_seconds == prev_info.utc_offset_seconds
            and mid_info.is_dst == prev_info.is_dst
        ):
            # Still in old state, transition is after mid
            start = mid
        else:
            # In new state, transition is before mid
            end = mid

    return end


def list_all_timezones(
    country_code: str | None = None, search: str | None = None
) -> list[TimezoneListEntry]:
    """List available IANA timezones with optional filtering.

    Args:
        country_code: Optional ISO 3166 country code filter
        search: Optional substring search filter

    Returns:
        List of TimezoneListEntry objects
    """
    all_zones = sorted(available_timezones())
    results: list[TimezoneListEntry] = []

    for tz_id in all_zones:
        # Skip deprecated zones
        if tz_id.startswith(DeprecatedTimezonePrefix.ETC) and tz_id not in [
            AllowedEtcTimezone.UTC,
            AllowedEtcTimezone.GMT,
        ]:
            continue

        # Apply search filter
        if search and search.lower() not in tz_id.lower():
            continue

        # Extract example city from zone ID
        parts = tz_id.split("/")
        example_city = parts[-1].replace("_", " ") if len(parts) > 1 else None

        # Try to infer country code from zone ID
        inferred_country = _infer_country_code(tz_id, parts)

        # Apply country filter
        if country_code and inferred_country != country_code:
            continue

        results.append(
            TimezoneListEntry(
                id=tz_id,
                country_code=inferred_country,
                comment=None,  # Would need zone1970.tab parsing for full data
                example_city=example_city,
            )
        )

    return results


def _infer_country_code(tz_id: str, parts: list[str]) -> str | None:
    """Infer country code from timezone ID.

    Args:
        tz_id: IANA timezone identifier
        parts: Split timezone ID parts

    Returns:
        ISO 3166 country code or None
    """
    if len(parts) < 2:
        return None

    region = parts[0]

    # Simple heuristic mapping (not exhaustive)
    if region == "America":
        if "New_York" in tz_id or "Chicago" in tz_id:
            return "US"
    elif region == "Europe":
        if "London" in tz_id:
            return "GB"
        elif "Paris" in tz_id:
            return "FR"
        elif "Berlin" in tz_id:
            return "DE"
    elif region == "Asia":
        if "Tokyo" in tz_id:
            return "JP"
        elif "Shanghai" in tz_id:
            return "CN"
        elif "Dubai" in tz_id:
            return "AE"
    elif region == "Australia":
        return "AU"

    return None


def convert_datetime_between_timezones(dt_str: str, from_tz: str, to_tz: str) -> TimezoneConversion:
    """Convert a datetime from one timezone to another.

    Args:
        dt_str: ISO 8601 datetime string (naive, will be interpreted in from_tz)
        from_tz: Source IANA timezone
        to_tz: Target IANA timezone

    Returns:
        TimezoneConversion object with conversion details
    """
    # Parse naive datetime (remove any timezone info)
    dt_str_naive = _remove_timezone_info(dt_str)
    naive_dt = datetime.fromisoformat(dt_str_naive)

    # Apply source timezone
    from_zone = ZoneInfo(from_tz)
    from_dt = naive_dt.replace(tzinfo=from_zone)

    # Convert to target timezone
    to_zone = ZoneInfo(to_tz)
    to_dt = from_dt.astimezone(to_zone)

    # Get offset info
    from_offset = from_dt.utcoffset()
    to_offset = to_dt.utcoffset()

    from_offset_seconds = int(from_offset.total_seconds()) if from_offset else 0
    to_offset_seconds = int(to_offset.total_seconds()) if to_offset else 0

    # Calculate difference
    offset_diff = to_offset_seconds - from_offset_seconds

    # Generate explanation
    explanation = _generate_conversion_explanation(
        from_tz, to_tz, from_offset_seconds, to_offset_seconds, offset_diff
    )

    return TimezoneConversion(
        from_timezone=from_tz,
        from_datetime=from_dt,
        from_utc_offset_seconds=from_offset_seconds,
        to_timezone=to_tz,
        to_datetime=to_dt,
        to_utc_offset_seconds=to_offset_seconds,
        offset_difference_seconds=offset_diff,
        explanation=explanation,
    )


def _remove_timezone_info(dt_str: str) -> str:
    """Remove timezone information from ISO 8601 datetime string.

    Args:
        dt_str: ISO 8601 datetime string

    Returns:
        Naive datetime string without timezone info
    """
    if "Z" in dt_str:
        return dt_str.replace("Z", "")
    elif "+" in dt_str:
        return dt_str.split("+")[0]
    elif dt_str.count("-") > 2:  # Has timezone offset like -05:00
        parts = dt_str.rsplit("-", 1)
        return parts[0]
    return dt_str


def _generate_conversion_explanation(
    from_tz: str, to_tz: str, from_offset_seconds: int, to_offset_seconds: int, offset_diff: int
) -> str:
    """Generate human-readable explanation of timezone conversion.

    Args:
        from_tz: Source timezone
        to_tz: Target timezone
        from_offset_seconds: Source offset in seconds
        to_offset_seconds: Target offset in seconds
        offset_diff: Difference in seconds

    Returns:
        Explanation string
    """
    hours_diff = offset_diff / 3600

    if hours_diff == 0:
        return f"Both timezones have the same UTC offset ({from_offset_seconds / 3600:+.1f} hours)"
    elif hours_diff > 0:
        return (
            f"{to_tz} is {abs(hours_diff):.1f} hours ahead of {from_tz} "
            f"(UTC{from_offset_seconds / 3600:+.1f} → UTC{to_offset_seconds / 3600:+.1f})"
        )
    else:
        return (
            f"{to_tz} is {abs(hours_diff):.1f} hours behind {from_tz} "
            f"(UTC{from_offset_seconds / 3600:+.1f} → UTC{to_offset_seconds / 3600:+.1f})"
        )
