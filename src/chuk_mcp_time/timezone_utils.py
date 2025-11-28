"""Timezone utilities using IANA tzdata."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones


def get_tzdata_version() -> str:
    """Get the IANA tzdata version.

    Returns:
        Version string (e.g., "2024b") or "unknown" if not available
    """
    try:
        # Try to get version from zoneinfo
        import importlib.metadata

        try:
            return importlib.metadata.version("tzdata")
        except importlib.metadata.PackageNotFoundError:
            pass

        # Fallback: try to read version from system tzdata
        # This is system-dependent and may not always work
        return "system"
    except Exception:
        return "unknown"


def get_timezone_info_at_datetime(tz_name: str, dt: datetime) -> dict[str, str | int | bool]:
    """Get timezone information at a specific datetime.

    Args:
        tz_name: IANA timezone identifier
        dt: Datetime to query (should be timezone-aware)

    Returns:
        Dictionary with utc_offset_seconds, is_dst, abbreviation
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

    return {
        "utc_offset_seconds": offset_seconds,
        "is_dst": is_dst,
        "abbreviation": abbreviation,
    }


def find_timezone_transitions(
    tz_name: str, start_dt: datetime, end_dt: datetime
) -> list[dict[str, str | int | bool]]:
    """Find timezone transitions in a date range.

    Args:
        tz_name: IANA timezone identifier
        start_dt: Start datetime (UTC)
        end_dt: End datetime (UTC)

    Returns:
        List of transitions with from_datetime, utc_offset_seconds, is_dst, abbreviation
    """
    transitions = []

    # Sample monthly to detect transitions
    current = start_dt
    prev_info = None

    while current <= end_dt:
        info = get_timezone_info_at_datetime(tz_name, current)

        # Check if offset or DST status changed
        if prev_info and (
            info["utc_offset_seconds"] != prev_info["utc_offset_seconds"]
            or info["is_dst"] != prev_info["is_dst"]
        ):
            # Transition detected, add it
            transitions.append(
                {
                    "from_datetime": current.isoformat(),
                    "utc_offset_seconds": info["utc_offset_seconds"],
                    "is_dst": info["is_dst"],
                    "abbreviation": info["abbreviation"],
                }
            )

        prev_info = info
        current += timedelta(days=30)  # Sample monthly

    return transitions


def list_all_timezones(
    country_code: str | None = None, search: str | None = None
) -> list[dict[str, str | None]]:
    """List available IANA timezones with optional filtering.

    Args:
        country_code: Optional ISO 3166 country code filter
        search: Optional substring search filter

    Returns:
        List of timezone info dictionaries
    """
    all_zones = sorted(available_timezones())
    results = []

    for tz_id in all_zones:
        # Skip deprecated zones
        if tz_id.startswith("Etc/") and tz_id not in [
            "Etc/UTC",
            "Etc/GMT",
        ]:
            continue

        # Apply search filter
        if search and search.lower() not in tz_id.lower():
            continue

        # Extract example city from zone ID
        parts = tz_id.split("/")
        example_city = parts[-1].replace("_", " ") if len(parts) > 1 else None

        # Try to infer country code from zone ID
        # This is a simple heuristic, not perfect
        inferred_country = None
        if len(parts) >= 2:
            region = parts[0]
            # Map regions to common country codes (simplified)
            if region == "America":
                # Would need full mapping, simplified here
                inferred_country = "US" if "New_York" in tz_id or "Chicago" in tz_id else None
            elif region == "Europe":
                if "London" in tz_id:
                    inferred_country = "GB"
                elif "Paris" in tz_id:
                    inferred_country = "FR"
                elif "Berlin" in tz_id:
                    inferred_country = "DE"
            elif region == "Asia":
                if "Tokyo" in tz_id:
                    inferred_country = "JP"
                elif "Shanghai" in tz_id:
                    inferred_country = "CN"
                elif "Dubai" in tz_id:
                    inferred_country = "AE"
            elif region == "Australia":
                inferred_country = "AU"

        # Apply country filter
        if country_code and inferred_country != country_code:
            continue

        results.append(
            {
                "id": tz_id,
                "country_code": inferred_country,
                "comment": None,  # Would need zone1970.tab parsing for full data
                "example_city": example_city,
            }
        )

    return results


def convert_datetime_between_timezones(
    dt_str: str, from_tz: str, to_tz: str
) -> dict[str, str | int]:
    """Convert a datetime from one timezone to another.

    Args:
        dt_str: ISO 8601 datetime string (naive, will be interpreted in from_tz)
        from_tz: Source IANA timezone
        to_tz: Target IANA timezone

    Returns:
        Dictionary with conversion details
    """
    # Parse naive datetime (remove any timezone info)
    # Handle Z, +, and - timezone indicators
    if "Z" in dt_str:
        dt_str_naive = dt_str.replace("Z", "")
    elif "+" in dt_str:
        dt_str_naive = dt_str.split("+")[0]
    elif dt_str.count("-") > 2:  # Has timezone offset like -05:00
        # Split on last occurrence of -
        parts = dt_str.rsplit("-", 1)
        dt_str_naive = parts[0]
    else:
        dt_str_naive = dt_str

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

    # Generate explanation
    offset_diff = to_offset_seconds - from_offset_seconds
    hours_diff = offset_diff / 3600

    if hours_diff == 0:
        explanation = (
            f"Both timezones have the same UTC offset ({from_offset_seconds / 3600:+.1f} hours)"
        )
    elif hours_diff > 0:
        explanation = (
            f"{to_tz} is {abs(hours_diff):.1f} hours ahead of {from_tz} "
            f"(UTC{from_offset_seconds / 3600:+.1f} → UTC{to_offset_seconds / 3600:+.1f})"
        )
    else:
        explanation = (
            f"{to_tz} is {abs(hours_diff):.1f} hours behind {from_tz} "
            f"(UTC{from_offset_seconds / 3600:+.1f} → UTC{to_offset_seconds / 3600:+.1f})"
        )

    return {
        "from_timezone": from_tz,
        "from_datetime": from_dt.isoformat(),
        "from_utc_offset_seconds": from_offset_seconds,
        "to_timezone": to_tz,
        "to_datetime": to_dt.isoformat(),
        "to_utc_offset_seconds": to_offset_seconds,
        "offset_difference_seconds": offset_diff,
        "explanation": explanation,
    }
