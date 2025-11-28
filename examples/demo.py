#!/usr/bin/env python3
"""Demo script to showcase chuk-mcp-time features and prove accuracy.

This script demonstrates:
1. Getting accurate UTC time with consensus
2. Comparing system clock vs trusted time
3. Converting to different timezones
4. Showing source transparency and error estimates
"""

import asyncio
import time
from datetime import datetime, timezone

from chuk_mcp_time.config import get_config
from chuk_mcp_time.consensus import TimeConsensusEngine
from chuk_mcp_time.ntp_client import NTPClient


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(label: str, value: str, indent: int = 0) -> None:
    """Print a formatted result line."""
    prefix = "  " * indent
    print(f"{prefix}{label:.<40} {value}")


async def demo_basic_time_query() -> None:
    """Demo 1: Get accurate UTC time with consensus."""
    print_header("Demo 1: Get Accurate UTC Time with NTP Consensus")

    config = get_config()
    ntp_client = NTPClient(timeout=config.ntp_timeout)
    consensus_engine = TimeConsensusEngine(
        max_outlier_deviation_ms=config.max_outlier_deviation_ms,
        min_sources=config.min_sources,
        max_disagreement_ms=config.max_disagreement_ms,
    )

    print(f"\nQuerying {len(config.ntp_servers)} NTP servers...")
    servers = config.ntp_servers[:4]  # Fast mode
    for server in servers:
        print(f"  • {server}")

    # Query servers
    start_time = time.time()
    responses = await ntp_client.query_multiple_servers(servers)
    query_time = (time.time() - start_time) * 1000

    # Compute consensus
    consensus = consensus_engine.compute_consensus(responses)

    print("\n📊 Results:")
    print_result("Consensus Time (UTC)", consensus.iso8601_time)
    print_result("Unix Timestamp (ms)", str(consensus.epoch_ms))
    print_result("Sources Used", f"{consensus.sources_used}/{consensus.total_sources}")
    print_result("Consensus Method", consensus.consensus_method.value)
    print_result("Estimated Error", f"±{consensus.estimated_error_ms:.1f} ms")
    print_result("Query Time", f"{query_time:.1f} ms")

    print("\n📡 Source Details:")
    for sample in consensus.source_samples:
        if sample.success:
            print(
                f"  ✅ {sample.server:30} "
                f"RTT: {sample.rtt_ms:5.1f}ms  "
                f"Stratum: {sample.stratum}"
            )
        else:
            print(f"  ❌ {sample.server:30} Error: {sample.error}")

    if consensus.warnings:
        print("\n⚠️  Warnings:")
        for warning in consensus.warnings:
            print(f"  • {warning}")


async def demo_system_clock_comparison() -> None:
    """Demo 2: Compare system clock vs trusted time."""
    print_header("Demo 2: System Clock Drift Detection")

    config = get_config()
    ntp_client = NTPClient(timeout=config.ntp_timeout)
    consensus_engine = TimeConsensusEngine()

    print("\nChecking system clock accuracy against NTP consensus...")

    # Get consensus time
    responses = await ntp_client.query_multiple_servers(config.ntp_servers[:4])
    consensus = consensus_engine.compute_consensus(responses)

    # Recalculate system delta with current system time (not the one captured during query)
    import time

    current_system_time = time.time()
    system_delta_ms = (current_system_time - consensus.timestamp) * 1000
    current_system_time_str = datetime.fromtimestamp(
        current_system_time, tz=timezone.utc
    ).isoformat()

    # Calculate status
    abs_delta = abs(system_delta_ms)
    if abs_delta < 100:
        status = "✅ OK"
        status_desc = "System clock is accurate"
    elif abs_delta < 1000:
        status = "⚠️  DRIFT"
        status_desc = "System clock has minor drift"
    else:
        status = "❌ ERROR"
        status_desc = "System clock has significant drift"

    print("\n🕐 Clock Comparison:")
    print_result("System Time", current_system_time_str)
    print_result("Trusted Time", consensus.iso8601_time)
    print_result("Delta", f"{system_delta_ms:+.1f} ms")
    print_result("Status", f"{status} - {status_desc}")
    print_result("Confidence", f"±{consensus.estimated_error_ms:.1f} ms")

    # Interpretation
    if system_delta_ms > 0:
        direction = "ahead (fast)"
    elif system_delta_ms < 0:
        direction = "behind (slow)"
    else:
        direction = "synchronized"

    print(f"\n💡 Your system clock is {abs_delta:.1f}ms {direction} of NTP consensus.")


async def demo_timezone_conversion() -> None:
    """Demo 3: Convert consensus time to different timezones."""
    print_header("Demo 3: Timezone Conversions")

    config = get_config()
    ntp_client = NTPClient(timeout=config.ntp_timeout)
    consensus_engine = TimeConsensusEngine()

    print("\nGetting consensus time and converting to timezones...")

    # Get consensus time
    responses = await ntp_client.query_multiple_servers(config.ntp_servers[:4])
    consensus = consensus_engine.compute_consensus(responses)

    # Convert to different timezones
    from zoneinfo import ZoneInfo

    timezones = [
        ("UTC", "UTC"),
        ("New York", "America/New_York"),
        ("London", "Europe/London"),
        ("Tokyo", "Asia/Tokyo"),
        ("Sydney", "Australia/Sydney"),
        ("Los Angeles", "America/Los_Angeles"),
    ]

    utc_timestamp = consensus.timestamp
    utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)

    print("\n🌍 Time Around the World (from same NTP consensus):")
    for city, tz_name in timezones:
        local_dt = utc_dt.astimezone(ZoneInfo(tz_name))
        print(f"  {city:15} {local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    print(
        f"\n💡 All times derived from single consensus (±{consensus.estimated_error_ms:.1f}ms accuracy)"
    )


async def demo_accuracy_visualization() -> None:
    """Demo 4: Visualize time accuracy across multiple samples."""
    print_header("Demo 4: Time Accuracy Visualization")

    config = get_config()
    ntp_client = NTPClient(timeout=config.ntp_timeout)
    consensus_engine = TimeConsensusEngine()

    print("\nTaking 5 consensus samples to demonstrate accuracy...")

    samples = []
    for i in range(5):
        print(f"  Sample {i+1}/5...", end=" ", flush=True)
        responses = await ntp_client.query_multiple_servers(config.ntp_servers[:4])
        consensus = consensus_engine.compute_consensus(responses)
        samples.append(consensus)
        print(f"✓ (±{consensus.estimated_error_ms:.1f}ms)")
        await asyncio.sleep(0.5)  # Brief delay between samples

    print("\n📈 Consensus Stability:")
    base_timestamp = samples[0].timestamp
    for i, sample in enumerate(samples, 1):
        delta_ms = (sample.timestamp - base_timestamp) * 1000
        bar_len = min(int(abs(delta_ms) / 10), 50)
        bar = "█" * bar_len if bar_len > 0 else ""
        print(f"  Sample {i}: {delta_ms:+8.1f}ms {bar}")

    # Calculate statistics
    timestamps = [s.timestamp for s in samples]
    avg_timestamp = sum(timestamps) / len(timestamps)
    deltas = [(t - avg_timestamp) * 1000 for t in timestamps]
    max_deviation = max(abs(d) for d in deltas)
    avg_error = sum(s.estimated_error_ms for s in samples) / len(samples)

    print("\n📊 Statistics:")
    print_result("Max Deviation", f"±{max_deviation:.1f} ms")
    print_result("Avg Error Estimate", f"±{avg_error:.1f} ms")
    print_result("Samples", str(len(samples)))

    print(
        f"\n💡 Consensus is stable within ±{max_deviation:.1f}ms across {len(samples)} samples"
    )


async def main() -> None:
    """Run all demos."""
    print("\n" + "🕐" * 35)
    print("  chuk-mcp-time Demo - High-Accuracy Time with NTP Consensus")
    print("🕐" * 35)

    try:
        await demo_basic_time_query()
        await demo_system_clock_comparison()
        await demo_timezone_conversion()
        await demo_accuracy_visualization()

        print_header("Summary")
        print("""
✅ Successfully demonstrated:
  • Querying multiple NTP servers with consensus
  • Outlier detection and removal
  • System clock drift detection
  • Timezone conversions
  • Accuracy estimation and stability

💡 Key Takeaways:
  • Typical accuracy: ±10-50ms (much better than system clock drift)
  • Consensus removes outliers automatically
  • All source data is transparent and auditable
  • Works independently of system clock
  • Suitable for most distributed systems, logging, and time-sensitive apps
        """)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
