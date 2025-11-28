# Examples

This directory contains example scripts demonstrating the features of `chuk-mcp-time`.

## Running the Demo

### Prerequisites

Make sure you have installed `chuk-mcp-time`:

```bash
# From the repository root
make dev-install

# Or with pip
pip install chuk-mcp-time
```

### Run the Demo

```bash
# From repository root
python examples/demo.py

# Or make it executable and run directly
chmod +x examples/demo.py
./examples/demo.py
```

## What the Demo Shows

### Demo 1: Get Accurate UTC Time with NTP Consensus

- Queries multiple NTP servers (Cloudflare, Google, Apple, pool.ntp.org)
- Shows round-trip times and stratum for each server
- Computes consensus time using median with outlier rejection
- Displays estimated error bounds

### Demo 2: System Clock Drift Detection

- Compares your system clock against NTP consensus (using current system time)
- Calculates the delta in milliseconds
- Provides status (OK, DRIFT, or ERROR)
- Shows if your clock is ahead (fast) or behind (slow)
- Helps identify clock synchronization issues

### Demo 3: Timezone Conversions

- Gets a single NTP consensus timestamp
- Converts to multiple timezones (New York, London, Tokyo, Sydney, etc.)
- Demonstrates consistency across timezones
- Shows all times derive from the same trusted source

### Demo 4: Time Accuracy Visualization

- Takes 5 consecutive consensus samples
- Shows stability and consistency
- Calculates max deviation and average error
- Visualizes time deltas with ASCII bars

## Expected Output

You should see output similar to:

```
======================================================================
  Demo 1: Get Accurate UTC Time with NTP Consensus
======================================================================

Querying 7 NTP servers...
  • time.cloudflare.com
  • time.google.com
  • time.apple.com
  • 0.pool.ntp.org

📊 Results:
Consensus Time (UTC).................... 2025-11-28T10:04:59.916227+00:00
Unix Timestamp (ms)..................... 1764324299916
Sources Used............................ 4/4
Consensus Method........................ median_with_outlier_rejection
Estimated Error......................... ±10.0 ms
Query Time.............................. 42.8 ms

📡 Source Details:
  ✅ time.cloudflare.com            RTT:  42.3ms  Stratum: 3
  ✅ time.google.com                RTT:  25.5ms  Stratum: 1
  ✅ time.apple.com                 RTT:  20.9ms  Stratum: 1
  ✅ 0.pool.ntp.org                 RTT:  24.9ms  Stratum: 3

======================================================================
  Demo 2: System Clock Drift Detection
======================================================================

🕐 Clock Comparison:
System Time............................. 2025-11-28T10:04:59.955721+00:00
Trusted Time............................ 2025-11-28T10:04:59.953370+00:00
Delta................................... +2.4 ms
Status.................................. ✅ OK - System clock is accurate
Confidence.............................. ±10.0 ms

💡 Your system clock is 2.4ms ahead (fast) of NTP consensus.
```

## Network Requirements

The demo requires internet access to query NTP servers. If you're behind a firewall, ensure UDP port 123 is open for NTP traffic.

## Troubleshooting

### "No NTP sources available" Error

- Check your internet connection
- Verify firewall allows UDP port 123
- Try running with fewer servers or different timeout:

```bash
TIME_SERVER_NTP_TIMEOUT=5.0 python examples/demo.py
```

### High Error Estimates

- Normal: ±10-50ms
- High network latency can increase error bounds
- Try running from a location with better connectivity

### Time Drift Warnings

If the demo shows your system clock has significant drift:

1. **Linux**: Run `sudo ntpdate -s time.google.com` or enable NTP daemon
2. **macOS**: System Preferences → Date & Time → "Set date and time automatically"
3. **Windows**: Settings → Time & Language → "Set time automatically"

## Using in Your Code

The demo shows how to use the library programmatically:

```python
import asyncio
from chuk_mcp_time.config import get_config
from chuk_mcp_time.consensus import TimeConsensusEngine
from chuk_mcp_time.ntp_client import NTPClient

async def get_accurate_time():
    config = get_config()
    ntp_client = NTPClient(timeout=config.ntp_timeout)
    consensus_engine = TimeConsensusEngine()

    # Query servers
    responses = await ntp_client.query_multiple_servers(config.ntp_servers[:4])

    # Get consensus
    consensus = consensus_engine.compute_consensus(responses)

    print(f"Accurate time: {consensus.iso8601_time}")
    print(f"Error: ±{consensus.estimated_error_ms:.1f}ms")

    return consensus

asyncio.run(get_accurate_time())
```

## More Examples

See the [README.md](../README.md) for more usage examples including:
- Integration with Claude Desktop
- HTTP server mode
- Docker deployment
- Configuration options
