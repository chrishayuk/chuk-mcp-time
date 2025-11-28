"""Consensus algorithm for determining accurate time from multiple sources."""

import statistics
import time
from datetime import UTC, datetime

from chuk_mcp_time.models import (
    ConsensusMethod,
    NTPResponse,
    SourceSample,
    TimeConsensus,
)


class TimeConsensusEngine:
    """Engine for computing time consensus from multiple sources."""

    def __init__(
        self,
        max_outlier_deviation_ms: float = 5000.0,
        min_sources: int = 3,
        max_disagreement_ms: float = 250.0,
    ) -> None:
        """Initialize consensus engine.

        Args:
            max_outlier_deviation_ms: Maximum deviation from median to reject as outlier
            min_sources: Minimum number of sources required for consensus
            max_disagreement_ms: Maximum disagreement before warning
        """
        self.max_outlier_deviation_ms = max_outlier_deviation_ms
        self.min_sources = min_sources
        self.max_disagreement_ms = max_disagreement_ms

    def compute_consensus(self, responses: list[NTPResponse]) -> TimeConsensus:
        """Compute time consensus from NTP responses.

        Args:
            responses: List of NTP responses from multiple servers

        Returns:
            TimeConsensus with consensus time and metadata
        """
        warnings: list[str] = []

        # Filter successful responses
        successful = [r for r in responses if r.success]

        if len(successful) < self.min_sources:
            warnings.append(
                f"Only {len(successful)} sources available (minimum {self.min_sources} recommended)"
            )

        if not successful:
            # Fallback to system time if no sources available
            system_time_float = time.time()
            return self._create_fallback_consensus(responses, system_time_float, warnings)

        # Adjust timestamps for RTT (add half the round-trip time)
        adjusted_times = []
        for r in successful:
            adjusted = r.timestamp + (r.rtt_ms / 2000.0)  # Convert ms to seconds
            adjusted_times.append(adjusted)

        # Remove outliers using iterative median filtering
        filtered_times, outliers_removed = self._remove_outliers(adjusted_times)

        if outliers_removed > 0:
            warnings.append(f"Removed {outliers_removed} outlier(s) from consensus")

        if len(filtered_times) < self.min_sources:
            warnings.append(f"After outlier removal, only {len(filtered_times)} sources remain")

        # Compute consensus time (median of filtered times)
        consensus_timestamp = statistics.median(filtered_times)

        # Compute error estimate (standard deviation or IQR)
        if len(filtered_times) >= 2:
            # Use IQR as error estimate (more robust than std dev)
            sorted_times = sorted(filtered_times)
            q1_idx = len(sorted_times) // 4
            q3_idx = (3 * len(sorted_times)) // 4
            q1 = sorted_times[q1_idx]
            q3 = sorted_times[q3_idx]
            iqr = (q3 - q1) * 1000  # Convert to ms
            estimated_error_ms = max(iqr, 10.0)  # At least 10ms error
        else:
            # Single source: use RTT as error estimate
            estimated_error_ms = successful[0].rtt_ms

        # Check for large disagreement
        if len(filtered_times) >= 2:
            time_range = (max(filtered_times) - min(filtered_times)) * 1000
            if time_range > self.max_disagreement_ms:
                warnings.append(f"Large disagreement between sources: {time_range:.1f}ms range")

        # Build source samples for transparency
        source_samples = [self._create_source_sample(r) for r in responses]

        # Get system time for comparison
        system_time_float = time.time()
        system_delta_ms = (system_time_float - consensus_timestamp) * 1000

        # Format times
        iso8601_time = datetime.fromtimestamp(consensus_timestamp, tz=UTC).isoformat()
        epoch_ms = int(consensus_timestamp * 1000)
        system_time_str = datetime.fromtimestamp(system_time_float, tz=UTC).isoformat()

        return TimeConsensus(
            timestamp=consensus_timestamp,
            iso8601_time=iso8601_time,
            epoch_ms=epoch_ms,
            sources_used=len(filtered_times),
            total_sources=len(responses),
            consensus_method=ConsensusMethod.MEDIAN_WITH_OUTLIER_REJECTION,
            estimated_error_ms=estimated_error_ms,
            source_samples=source_samples,
            warnings=warnings,
            system_time=system_time_str,
            system_delta_ms=system_delta_ms,
        )

    def _remove_outliers(self, times: list[float]) -> tuple[list[float], int]:
        """Remove outliers using iterative median filtering.

        Args:
            times: List of timestamps

        Returns:
            Tuple of (filtered_times, outliers_removed_count)
        """
        if len(times) < 3:
            return times, 0

        filtered = times.copy()
        outliers_removed = 0

        # Iteratively remove outliers
        max_iterations = 3
        for _ in range(max_iterations):
            if len(filtered) < 3:
                break

            median_time = statistics.median(filtered)
            max_dev_seconds = self.max_outlier_deviation_ms / 1000.0

            # Find times within acceptable deviation
            new_filtered = [t for t in filtered if abs(t - median_time) <= max_dev_seconds]

            if len(new_filtered) == len(filtered):
                # No more outliers found
                break

            outliers_removed += len(filtered) - len(new_filtered)
            filtered = new_filtered

        return filtered, outliers_removed

    def _create_source_sample(self, response: NTPResponse) -> SourceSample:
        """Create a source sample from an NTP response.

        Args:
            response: NTP response

        Returns:
            SourceSample with relevant fields
        """
        if response.success:
            return SourceSample(
                server=response.server,
                success=True,
                timestamp=response.timestamp,
                rtt_ms=response.rtt_ms,
                stratum=response.stratum,
            )
        else:
            return SourceSample(
                server=response.server,
                success=False,
                error=response.error,
            )

    def _create_fallback_consensus(
        self, responses: list[NTPResponse], system_time: float, warnings: list[str]
    ) -> TimeConsensus:
        """Create fallback consensus using system time.

        Args:
            responses: Original responses (for source samples)
            system_time: System timestamp
            warnings: Existing warnings

        Returns:
            TimeConsensus using system time
        """
        warnings.append("No NTP sources available, falling back to system time")

        iso8601_time = datetime.fromtimestamp(system_time, tz=UTC).isoformat()
        epoch_ms = int(system_time * 1000)

        source_samples = [self._create_source_sample(r) for r in responses]

        return TimeConsensus(
            timestamp=system_time,
            iso8601_time=iso8601_time,
            epoch_ms=epoch_ms,
            sources_used=0,
            total_sources=len(responses),
            consensus_method=ConsensusMethod.SYSTEM_FALLBACK,
            estimated_error_ms=999999.9,  # Unknown error
            source_samples=source_samples,
            warnings=warnings,
            system_time=iso8601_time,
            system_delta_ms=0.0,
        )
