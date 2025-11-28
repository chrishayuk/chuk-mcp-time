"""Tests for consensus algorithm."""

import time

from chuk_mcp_time.consensus import TimeConsensusEngine
from chuk_mcp_time.models import ConsensusMethod, NTPResponse


def create_successful_response(server: str, timestamp: float, rtt_ms: float = 10.0) -> NTPResponse:
    """Create a successful NTP response."""
    return NTPResponse(
        server=server,
        timestamp=timestamp,
        rtt_ms=rtt_ms,
        stratum=2,
        success=True,
    )


def create_failed_response(server: str, error: str = "Test error") -> NTPResponse:
    """Create a failed NTP response."""
    return NTPResponse(
        server=server,
        timestamp=0.0,
        rtt_ms=0.0,
        stratum=0,
        success=False,
        error=error,
    )


def test_consensus_with_all_successful_responses() -> None:
    """Test consensus with all successful responses."""
    engine = TimeConsensusEngine()
    base_time = time.time()

    responses = [
        create_successful_response("server1", base_time),
        create_successful_response("server2", base_time + 0.001),
        create_successful_response("server3", base_time - 0.001),
        create_successful_response("server4", base_time + 0.002),
    ]

    consensus = engine.compute_consensus(responses)

    assert consensus.sources_used >= 3
    assert consensus.total_sources == 4
    assert consensus.consensus_method == ConsensusMethod.MEDIAN_WITH_OUTLIER_REJECTION
    assert abs(consensus.timestamp - base_time) < 0.01  # Within 10ms
    assert len(consensus.warnings) == 0


def test_consensus_with_outliers() -> None:
    """Test consensus removes outliers."""
    engine = TimeConsensusEngine(max_outlier_deviation_ms=100.0)
    base_time = time.time()

    responses = [
        create_successful_response("server1", base_time),
        create_successful_response("server2", base_time + 0.001),
        create_successful_response("server3", base_time - 0.001),
        create_successful_response("server4", base_time + 10.0),  # Outlier
    ]

    consensus = engine.compute_consensus(responses)

    assert consensus.sources_used == 3  # One outlier removed
    assert "outlier" in " ".join(consensus.warnings).lower()
    assert abs(consensus.timestamp - base_time) < 0.01


def test_consensus_with_insufficient_sources() -> None:
    """Test consensus with insufficient sources."""
    engine = TimeConsensusEngine(min_sources=3)
    base_time = time.time()

    responses = [
        create_successful_response("server1", base_time),
        create_successful_response("server2", base_time + 0.001),
    ]

    consensus = engine.compute_consensus(responses)

    assert consensus.sources_used == 2
    assert any("Only 2 sources available" in w for w in consensus.warnings)


def test_consensus_with_all_failed_responses() -> None:
    """Test consensus falls back to system time when all responses fail."""
    engine = TimeConsensusEngine()

    responses = [
        create_failed_response("server1", "Timeout"),
        create_failed_response("server2", "DNS error"),
        create_failed_response("server3", "Network error"),
    ]

    consensus = engine.compute_consensus(responses)

    assert consensus.sources_used == 0
    assert consensus.consensus_method == ConsensusMethod.SYSTEM_FALLBACK
    assert any("No NTP sources available" in w for w in consensus.warnings)
    assert consensus.estimated_error_ms > 1000  # Very high error


def test_consensus_with_mixed_responses() -> None:
    """Test consensus with both successful and failed responses."""
    engine = TimeConsensusEngine()
    base_time = time.time()

    responses = [
        create_successful_response("server1", base_time),
        create_failed_response("server2", "Timeout"),
        create_successful_response("server3", base_time + 0.001),
        create_successful_response("server4", base_time - 0.001),
    ]

    consensus = engine.compute_consensus(responses)

    assert consensus.sources_used == 3
    assert consensus.total_sources == 4
    assert len(consensus.source_samples) == 4
    assert abs(consensus.timestamp - base_time) < 0.01


def test_consensus_with_large_disagreement() -> None:
    """Test consensus detects large disagreement between sources."""
    engine = TimeConsensusEngine(max_disagreement_ms=100.0)
    base_time = time.time()

    responses = [
        create_successful_response("server1", base_time),
        create_successful_response("server2", base_time + 0.150),  # 150ms apart
        create_successful_response("server3", base_time + 0.300),  # 300ms apart
    ]

    consensus = engine.compute_consensus(responses)

    assert any("disagreement" in w.lower() for w in consensus.warnings)


def test_consensus_source_samples() -> None:
    """Test consensus includes detailed source samples."""
    engine = TimeConsensusEngine()
    base_time = time.time()

    responses = [
        create_successful_response("server1", base_time, rtt_ms=15.0),
        create_failed_response("server2", "Timeout"),
    ]

    consensus = engine.compute_consensus(responses)

    assert len(consensus.source_samples) == 2

    # Check successful sample
    successful = next(s for s in consensus.source_samples if s.success)
    assert successful.server == "server1"
    assert successful.timestamp is not None
    assert successful.rtt_ms == 15.0
    assert successful.stratum == 2

    # Check failed sample
    failed = next(s for s in consensus.source_samples if not s.success)
    assert failed.server == "server2"
    assert failed.error == "Timeout"
    assert failed.timestamp is None


def test_consensus_system_delta() -> None:
    """Test consensus calculates system clock delta."""
    engine = TimeConsensusEngine()
    base_time = time.time()

    responses = [
        create_successful_response("server1", base_time),
        create_successful_response("server2", base_time + 0.001),
        create_successful_response("server3", base_time - 0.001),
    ]

    consensus = engine.compute_consensus(responses)

    # System delta should be small (within a few hundred milliseconds)
    assert abs(consensus.system_delta_ms) < 1000


def test_consensus_error_estimation() -> None:
    """Test consensus estimates error correctly."""
    engine = TimeConsensusEngine()
    base_time = time.time()

    # Tightly clustered times - low error
    responses = [
        create_successful_response("server1", base_time, rtt_ms=5.0),
        create_successful_response("server2", base_time + 0.001, rtt_ms=5.0),
        create_successful_response("server3", base_time - 0.001, rtt_ms=5.0),
    ]

    consensus = engine.compute_consensus(responses)
    assert consensus.estimated_error_ms < 50  # Should be low

    # Widely dispersed times - higher error
    responses2 = [
        create_successful_response("server1", base_time, rtt_ms=5.0),
        create_successful_response("server2", base_time + 0.100, rtt_ms=5.0),
        create_successful_response("server3", base_time - 0.100, rtt_ms=5.0),
    ]

    consensus2 = engine.compute_consensus(responses2)
    assert consensus2.estimated_error_ms > consensus.estimated_error_ms
