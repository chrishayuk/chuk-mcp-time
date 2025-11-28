"""High-accuracy time oracle MCP server using NTP consensus."""

__version__ = "1.0.0"

from chuk_mcp_time.server import (
    compare_system_clock,
    get_time_for_timezone,
    get_time_utc,
    main,
)

__all__ = [
    "get_time_utc",
    "get_time_for_timezone",
    "compare_system_clock",
    "main",
    "__version__",
]
