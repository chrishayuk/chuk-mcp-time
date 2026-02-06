"""Tests for NTP client."""

import pytest

from chuk_mcp_time.models import NTPError
from chuk_mcp_time.ntp_client import NTPClient


@pytest.mark.asyncio
@pytest.mark.network
async def test_query_single_server_success() -> None:
    """Test querying a single NTP server successfully."""
    client = NTPClient(timeout=5.0)
    response = await client.query_server("time.google.com")

    assert response.success
    assert response.server == "time.google.com"
    assert response.timestamp > 0
    assert response.rtt_ms > 0
    assert response.stratum > 0
    assert response.error is None


@pytest.mark.asyncio
async def test_query_invalid_server() -> None:
    """Test querying an invalid server."""
    client = NTPClient(timeout=1.0)
    response = await client.query_server("invalid.nonexistent.domain.xyz")

    assert not response.success
    assert response.error is not None
    # Error type can be either DNS_ERROR or TIMEOUT depending on DNS resolution behavior
    assert response.error_type in (NTPError.DNS_ERROR, NTPError.TIMEOUT)


@pytest.mark.asyncio
async def test_query_timeout() -> None:
    """Test timeout on non-responsive server."""
    client = NTPClient(timeout=0.1)
    # Use a non-routable IP to trigger timeout
    response = await client.query_server("192.0.2.1")

    assert not response.success
    assert response.error_type == NTPError.TIMEOUT


@pytest.mark.asyncio
@pytest.mark.network
async def test_query_multiple_servers() -> None:
    """Test querying multiple NTP servers concurrently."""
    client = NTPClient(timeout=5.0)
    servers = ["time.google.com", "time.cloudflare.com", "time.apple.com"]

    responses = await client.query_multiple_servers(servers)

    assert len(responses) == 3
    # At least some should succeed
    successful = [r for r in responses if r.success]
    assert len(successful) >= 1


@pytest.mark.asyncio
@pytest.mark.network
async def test_query_multiple_servers_with_failures() -> None:
    """Test querying multiple servers including some that fail."""
    client = NTPClient(timeout=2.0)
    servers = [
        "time.google.com",
        "invalid.nonexistent.domain.xyz",
        "time.cloudflare.com",
    ]

    responses = await client.query_multiple_servers(servers)

    assert len(responses) == 3

    successful = [r for r in responses if r.success]
    failed = [r for r in responses if not r.success]

    # Should have at least one success and one failure
    assert len(successful) >= 1
    assert len(failed) >= 1

    # Check failed response has error
    assert all(r.error is not None for r in failed)


def test_ntp_client_initialization() -> None:
    """Test NTP client initialization."""
    client = NTPClient(timeout=3.0)
    assert client.timeout == 3.0
    assert client.NTP_PORT == 123
    assert client.NTP_VERSION == 3


@pytest.mark.asyncio
async def test_query_network_error() -> None:
    """Test handling of network errors."""
    client = NTPClient(timeout=0.1)
    # Use localhost on wrong port to trigger network error
    response = await client.query_server("127.0.0.1")

    assert not response.success
    assert response.error is not None
    # Could be timeout or network error depending on system
    assert response.error_type in (NTPError.TIMEOUT, NTPError.NETWORK_ERROR)


@pytest.mark.asyncio
async def test_query_dns_error() -> None:
    """Test handling of DNS resolution errors."""
    from unittest.mock import patch

    client = NTPClient(timeout=1.0)

    # Mock socket.getaddrinfo to raise gaierror
    import socket

    with patch("socket.getaddrinfo", side_effect=socket.gaierror("DNS lookup failed")):
        response = await client.query_server("some-host.example.com")

    assert not response.success
    assert response.error_type == NTPError.DNS_ERROR
    assert "DNS resolution failed" in response.error


@pytest.mark.asyncio
async def test_query_oserror() -> None:
    """Test handling of OSError."""
    from unittest.mock import patch

    client = NTPClient(timeout=1.0)

    # Mock socket.socket to raise OSError
    with patch("socket.socket", side_effect=OSError("Network unreachable")):
        response = await client.query_server("time.google.com")

    assert not response.success
    assert response.error_type == NTPError.NETWORK_ERROR
    assert "Network error" in response.error


@pytest.mark.asyncio
async def test_query_unexpected_exception() -> None:
    """Test handling of unexpected exceptions."""
    from unittest.mock import patch

    client = NTPClient(timeout=1.0)

    # Mock socket.socket to raise unexpected exception
    with patch("socket.socket", side_effect=RuntimeError("Unexpected error")):
        response = await client.query_server("time.google.com")

    assert not response.success
    assert response.error_type == NTPError.PARSE_ERROR
    assert "Parse error" in response.error


@pytest.mark.asyncio
@pytest.mark.network
async def test_query_multiple_servers_concurrent() -> None:
    """Test that multiple servers are queried concurrently."""
    import time

    client = NTPClient(timeout=5.0)
    servers = ["time.google.com", "time.cloudflare.com", "time.apple.com"]

    start = time.time()
    responses = await client.query_multiple_servers(servers)
    elapsed = time.time() - start

    # If queries were concurrent, total time should be less than sum of individual times
    # Each query might take ~100ms, but concurrent should be ~100ms total, not 300ms
    # Use 6.0 seconds to account for network variability (timeout is 5.0)
    assert elapsed < 6.0  # Should complete in under 6 seconds (allows for timeout + overhead)
    assert len(responses) == 3
