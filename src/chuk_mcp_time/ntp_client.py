"""Async NTP client for querying multiple NTP servers."""

import asyncio
import socket
import struct
import time

from chuk_mcp_time.models import NTPError, NTPResponse


class NTPClient:
    """Async NTP client for querying time servers."""

    # NTP packet format constants
    NTP_PACKET_FORMAT = "!12I"
    NTP_DELTA = 2208988800  # Seconds between 1900 and 1970
    NTP_PORT = 123
    NTP_VERSION = 3
    NTP_MODE_CLIENT = 3

    def __init__(self, timeout: float = 2.0) -> None:
        """Initialize NTP client.

        Args:
            timeout: Socket timeout in seconds
        """
        self.timeout = timeout

    async def query_server(self, server: str) -> NTPResponse:
        """Query a single NTP server asynchronously.

        Args:
            server: NTP server hostname or IP

        Returns:
            NTPResponse with time data or error information
        """
        try:
            # Create NTP request packet
            ntp_packet = bytearray(48)
            ntp_packet[0] = (self.NTP_VERSION << 3) | self.NTP_MODE_CLIENT

            # Use asyncio to create UDP connection
            loop = asyncio.get_event_loop()

            # Run socket operations in executor to avoid blocking
            def sync_query() -> tuple[bytes, float]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(self.timeout)
                try:
                    t0 = time.time()
                    sock.sendto(ntp_packet, (server, self.NTP_PORT))
                    response, _ = sock.recvfrom(1024)
                    t1 = time.time()
                    return response, (t1 - t0) * 1000
                finally:
                    sock.close()

            response, rtt_ms = await loop.run_in_executor(None, sync_query)

            # Parse NTP response
            unpacked = struct.unpack(self.NTP_PACKET_FORMAT, response)

            # Extract transmit timestamp (fields 10-11)
            tx_timestamp_int = unpacked[10]
            tx_timestamp_frac = unpacked[11]

            # Convert to Unix timestamp
            tx_timestamp = tx_timestamp_int + (tx_timestamp_frac / 2**32)
            unix_timestamp = tx_timestamp - self.NTP_DELTA

            # Extract stratum (quality indicator)
            stratum = (unpacked[0] >> 16) & 0xFF

            return NTPResponse(
                server=server,
                timestamp=unix_timestamp,
                rtt_ms=rtt_ms,
                stratum=stratum,
                success=True,
            )

        except TimeoutError:
            return NTPResponse(
                server=server,
                timestamp=0.0,
                rtt_ms=0.0,
                stratum=0,
                success=False,
                error="Request timed out",
                error_type=NTPError.TIMEOUT,
            )
        except socket.gaierror as e:
            return NTPResponse(
                server=server,
                timestamp=0.0,
                rtt_ms=0.0,
                stratum=0,
                success=False,
                error=f"DNS resolution failed: {e}",
                error_type=NTPError.DNS_ERROR,
            )
        except OSError as e:
            return NTPResponse(
                server=server,
                timestamp=0.0,
                rtt_ms=0.0,
                stratum=0,
                success=False,
                error=f"Network error: {e}",
                error_type=NTPError.NETWORK_ERROR,
            )
        except Exception as e:
            return NTPResponse(
                server=server,
                timestamp=0.0,
                rtt_ms=0.0,
                stratum=0,
                success=False,
                error=f"Parse error: {e}",
                error_type=NTPError.PARSE_ERROR,
            )

    async def query_multiple_servers(self, servers: list[str]) -> list[NTPResponse]:
        """Query multiple NTP servers concurrently.

        Args:
            servers: List of NTP server hostnames

        Returns:
            List of NTP responses (both successful and failed)
        """
        tasks = [self.query_server(server) for server in servers]
        responses = await asyncio.gather(*tasks, return_exceptions=False)
        return list(responses)
