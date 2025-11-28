# chuk-mcp-time

**High-accuracy time oracle MCP server using NTP consensus**

A Model Context Protocol (MCP) server that provides extremely accurate time information by querying multiple NTP servers, removing outliers, and computing a consensus time independent of the system clock. Perfect for applications requiring trusted time sources, detecting clock drift, or working in environments where system clocks may be unreliable.

[![Test](https://github.com/chuk-ai/chuk-mcp-time/workflows/Test/badge.svg)](https://github.com/chuk-ai/chuk-mcp-time/actions)
[![PyPI version](https://badge.fury.io/py/chuk-mcp-time.svg)](https://badge.fury.io/py/chuk-mcp-time)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Features

🎯 **Multi-Source Consensus**: Queries 4-7 NTP servers simultaneously and computes consensus time using median with outlier rejection

⚡ **Async-First**: Built on asyncio for maximum performance with concurrent NTP queries

⏱️ **Latency Compensation**: Automatically adjusts timestamps for query duration so returned time represents "now"

🔒 **Type-Safe**: 100% Pydantic models with full type hints and validation using enums

🌍 **Timezone Support**: Convert consensus time to any IANA timezone

🔍 **Clock Drift Detection**: Compare system clock against trusted NTP sources

📊 **Transparent**: Returns all source data, consensus method, error estimates, and query duration

⚙️ **Configurable**: Environment-based configuration for NTP servers and consensus parameters

🚀 **Production-Ready**: Docker support, GitHub Actions CI/CD, Fly.io deployment

## Installation

### Using uvx (recommended)

```bash
uvx chuk-mcp-time
```

### Using pip

```bash
pip install chuk-mcp-time
```

### From source

```bash
git clone https://github.com/chuk-ai/chuk-mcp-time.git
cd chuk-mcp-time
make dev-install
```

## Demo

See the server in action with a comprehensive demo:

```bash
# Run the demo script
uv run examples/demo.py

# Or with Python
python examples/demo.py
```

The demo shows:
- ✅ Querying 4 NTP servers with consensus
- ✅ System clock drift detection (detects ±millisecond accuracy)
- ✅ Timezone conversions (6 timezones from single consensus)
- ✅ Stability across 5 samples

**Example output:**
```
📊 Results:
Consensus Time (UTC).................... 2025-11-28T10:04:59.916227+00:00
Sources Used............................ 4/4
Estimated Error......................... ±10.0 ms
Query Time.............................. 42.8 ms

🕐 Clock Comparison:
Delta................................... +2.4 ms
Status.................................. ✅ OK - System clock is accurate
```

See [examples/README.md](examples/README.md) for detailed demo documentation.

## Quick Start

### As MCP Server (STDIO)

```bash
# Run with default settings (STDIO transport for Claude Desktop, mcp-cli, etc.)
chuk-mcp-time

# Or using Python module
python -m chuk_mcp_time.server
```

### As HTTP Server

```bash
# Run in HTTP mode for testing/development
chuk-mcp-time http

# Or
python -m chuk_mcp_time.server http
```

### With Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "time": {
      "command": "uvx",
      "args": ["chuk-mcp-time"]
    }
  }
}
```

## Available Tools

### 1. `get_time_utc`

Get current UTC time with high accuracy using NTP consensus.

**Parameters:**
- `mode` (optional): `"fast"` (default, 4 servers) or `"accurate"` (7 servers)
- `compensate_latency` (optional): `true` (default) to adjust timestamp for query duration

**Returns:**
```json
{
  "iso8601_time": "2025-11-28T01:23:45.123456+00:00",
  "epoch_ms": 1732756425123,
  "sources_used": 4,
  "total_sources": 4,
  "consensus_method": "median_with_outlier_rejection",
  "estimated_error_ms": 12.5,
  "source_samples": [...],
  "warnings": ["Applied +150.2ms latency compensation to timestamp"],
  "system_time": "2025-11-28T01:23:49.456789+00:00",
  "system_delta_ms": 4333.333,
  "query_duration_ms": 150.2,
  "latency_compensated": true
}
```

**Latency Compensation:**
By default, the timestamp is adjusted to account for the time spent querying NTP servers. This means the returned timestamp represents "now" (when the response is sent), not when the NTP queries started. This is especially important for slow networks or accurate mode.

### 2. `get_time_for_timezone`

Get current time for a specific timezone with high accuracy.

**Parameters:**
- `timezone_name`: IANA timezone name (e.g., `"America/New_York"`, `"Europe/London"`)
- `mode` (optional): `"fast"` or `"accurate"`
- `compensate_latency` (optional): `true` (default) to adjust timestamp for query duration

**Returns:**
Same as `get_time_utc` plus:
```json
{
  "timezone": "America/New_York",
  "local_time": "2025-11-27T20:23:45.123456-05:00"
}
```

### 3. `compare_system_clock`

Compare system clock against trusted NTP sources to detect drift.

**Parameters:**
- `mode` (optional): `"fast"` or `"accurate"`

**Returns:**
```json
{
  "system_time": "2025-11-28T01:23:49.456789+00:00",
  "trusted_time": "2025-11-28T01:23:45.123456+00:00",
  "delta_ms": 4333.333,
  "estimated_error_ms": 12.5,
  "status": "error"
}
```

Status values:
- `"ok"`: Delta < 100ms
- `"drift"`: Delta 100-1000ms
- `"error"`: Delta > 1000ms

## Configuration

Configuration can be set via environment variables or `.env` file:

```bash
# NTP Servers (comma-separated)
TIME_SERVER_NTP_SERVERS=time.cloudflare.com,time.google.com,time.apple.com

# NTP timeout in seconds (0.5 to 10.0)
TIME_SERVER_NTP_TIMEOUT=2.0

# Maximum outlier deviation in milliseconds (100.0 to 60000.0)
TIME_SERVER_MAX_OUTLIER_DEVIATION_MS=5000.0

# Minimum number of sources required (1 to 10)
TIME_SERVER_MIN_SOURCES=3

# Maximum disagreement before warning in milliseconds (10.0 to 5000.0)
TIME_SERVER_MAX_DISAGREEMENT_MS=250.0

# Number of servers to query in fast mode (2 to 10)
TIME_SERVER_FAST_MODE_SERVER_COUNT=4
```

See [.env.example](.env.example) for complete configuration template.

## How It Works

### Consensus Algorithm

1. **Query Multiple Sources**: Queries 4-7 NTP servers concurrently based on mode
2. **RTT Adjustment**: Adjusts timestamps by adding half the round-trip time
3. **Outlier Removal**: Iteratively removes outliers > 5 seconds from median
4. **Median Consensus**: Computes median of remaining timestamps
5. **Error Estimation**: Calculates IQR (interquartile range) as error estimate
6. **Latency Compensation**: Adds query duration to timestamp so result represents "now"
7. **System Comparison**: Compares consensus against system clock

### Latency Compensation

The server tracks how long it takes to query NTP servers and compute consensus (typically 100-500ms). By default, this duration is added to the consensus timestamp, so the returned time represents when the response is sent, not when queries began.

**Example:**
- Query starts at T+0ms
- NTP consensus computed at T+150ms → timestamp = 12:00:00.000
- Latency compensation: 12:00:00.000 + 150ms = 12:00:00.150
- Response sent at T+150ms with timestamp 12:00:00.150

This ensures the timestamp is as accurate as possible when received by the caller. You can disable this with `compensate_latency=false` if you prefer the raw consensus timestamp.

### Default NTP Servers

- `time.cloudflare.com` - Cloudflare's anycast NTP
- `time.google.com` - Google's public NTP
- `time.apple.com` - Apple's NTP servers
- `0-3.pool.ntp.org` - NTP Pool Project servers

All servers are stratum 1-2 for maximum accuracy.

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/chuk-ai/chuk-mcp-time.git
cd chuk-mcp-time

# Install development dependencies
make dev-install
```

### Testing

```bash
# Run tests (skip network tests)
make test

# Run tests with coverage
make test-cov

# Run all tests including network tests
pytest -v

# Run specific test
pytest tests/test_consensus.py -v
```

### Code Quality

```bash
# Run linter
make lint

# Auto-format code
make format

# Type checking
make typecheck

# Security checks
make security

# Run all checks
make check
```

### Building

```bash
# Build distribution packages
uv build

# Build Docker image
make docker-build

# Run Docker container
make docker-run
```

## Deployment

### Fly.io

```bash
# Deploy to Fly.io
flyctl deploy

# Or use GitHub Actions (push to main branch)
git push origin main
```

### Docker

```bash
# Build image
docker build -t chuk-mcp-time .

# Run container
docker run -p 8000:8000 chuk-mcp-time

# With custom config
docker run -p 8000:8000 \
  -e TIME_SERVER_NTP_TIMEOUT=5.0 \
  -e TIME_SERVER_MIN_SOURCES=5 \
  chuk-mcp-time
```

## Architecture

```
chuk-mcp-time/
├── src/chuk_mcp_time/
│   ├── __init__.py
│   ├── config.py          # Pydantic Settings configuration
│   ├── models.py          # Pydantic models (enums, responses)
│   ├── ntp_client.py      # Async NTP client
│   ├── consensus.py       # Consensus algorithm engine
│   └── server.py          # MCP server with tools
├── tests/
│   ├── test_config.py
│   ├── test_consensus.py
│   └── test_ntp_client.py
├── pyproject.toml
├── Makefile
├── Dockerfile
├── fly.toml
└── README.md
```

## Use Cases

### 1. Detecting Clock Drift

```python
# Use compare_system_clock to monitor clock health
response = await compare_system_clock(mode="accurate")

if response.status == "error":
    print(f"⚠️  System clock is off by {response.delta_ms:.1f}ms!")
    # Take corrective action...
```

### 2. Trusted Timestamps for Logs

```python
# Get consensus time for reliable logging
time_info = await get_time_utc(mode="fast")

log_entry = {
    "event": "user_login",
    "timestamp": time_info.iso8601_time,
    "source_count": time_info.sources_used,
    "error_ms": time_info.estimated_error_ms
}
```

### 3. Multi-Region Time Coordination

```python
# Get time for different regions
ny_time = await get_time_for_timezone("America/New_York")
london_time = await get_time_for_timezone("Europe/London")
tokyo_time = await get_time_for_timezone("Asia/Tokyo")

# All from the same NTP consensus - guaranteed consistency
```

### 4. Financial/Trading Applications

```python
# High-accuracy mode for financial operations
time_info = await get_time_utc(mode="accurate")

if time_info.estimated_error_ms < 20:
    # Error < 20ms, safe to use for timestamp-sensitive operations
    execute_trade(timestamp=time_info.epoch_ms)
else:
    # Too much uncertainty, defer or use alternative timing
    log_warning("Time uncertainty too high", error_ms=time_info.estimated_error_ms)
```

## Why Use This Over System Time?

### Problems with System Clocks

- **Drift**: System clocks drift over time (typically 10-50 ppm)
- **Virtualization**: VMs can have severe time skew
- **Containers**: Docker containers inherit host clock issues
- **Development**: Dev machines often have incorrect time
- **Distributed Systems**: Hard to trust time across multiple hosts

### This Solution Provides

- **Independent Verification**: Multiple external sources
- **Outlier Detection**: Automatic removal of bad sources
- **Transparency**: See all source data and warnings
- **Error Bounds**: Know the accuracy of the time
- **Auditability**: Full data for debugging time issues

## Performance

- **Fast Mode**: ~40-150ms (queries 4 servers)
- **Accurate Mode**: ~100-300ms (queries 7 servers)
- **Typical Accuracy**: ±10-50ms (much better than system clock drift)
- **Throughput**: Limited by NTP query rate (recommend caching for high-frequency use)

### Latency Breakdown

- NTP queries (concurrent): 20-100ms per server
- Consensus calculation: <1ms
- Latency compensation: Automatically added to timestamp
- Total round-trip: 40-300ms depending on mode and network

## Limitations

- **Network Required**: Requires internet access to NTP servers
- **Latency**: 100-500ms per query (not suitable for microsecond precision)
- **Rate Limiting**: Don't query too frequently (respect NTP pool guidelines)
- **Accuracy**: ±10-50ms typical (good enough for most applications, not atomic clock precision)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run `make check` to ensure quality
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details

## Credits

Built with:
- [chuk-mcp-server](https://github.com/chuk-ai/chuk-mcp-server) - High-performance MCP server framework
- [Pydantic](https://pydantic.dev) - Data validation using Python type hints
- NTP Pool Project servers

## Support

- 🐛 Issues: [GitHub Issues](https://github.com/chuk-ai/chuk-mcp-time/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/chuk-ai/chuk-mcp-time/discussions)
- 📧 Email: chris@chuk.ai

---

**Made with ❤️ by the Chuk AI team**
