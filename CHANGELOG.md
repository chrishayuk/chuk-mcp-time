# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-28

### Added

- Initial release of chuk-mcp-time
- Multi-source NTP consensus algorithm with outlier rejection
- Async NTP client supporting concurrent queries to 4-7 servers
- Three MCP tools:
  - `get_time_utc`: Get accurate UTC time with consensus
  - `get_time_for_timezone`: Convert to any IANA timezone
  - `compare_system_clock`: Detect system clock drift
- Latency compensation feature (automatically adjusts timestamp for query duration)
- Pydantic-native models with proper enums (AccuracyMode, ConsensusMethod, ClockStatus, NTPError)
- Environment-based configuration using Pydantic Settings
- Support for both stdio and http transports
- Comprehensive demo script showcasing all features
- Full test suite with pytest
- Docker support with multi-stage build
- GitHub Actions workflows (test, publish, release, fly-deploy)
- Fly.io deployment configuration
- Makefile with development, testing, and release targets
- Complete documentation with examples

### Features

- **Accuracy**: ±10-50ms typical (stratum 1-2 NTP servers)
- **Speed**: 40-150ms (fast mode), 100-300ms (accurate mode)
- **Consensus**: Median with iterative outlier rejection
- **Error Estimation**: IQR-based error bounds
- **Transparency**: Full source data, warnings, and metadata
- **Configurable**: 7 default NTP servers (Cloudflare, Google, Apple, pool.ntp.org)

### Architecture

- Async-first design using asyncio
- Type-safe with 100% Pydantic models
- Modular structure:
  - `models.py`: All Pydantic models and enums
  - `config.py`: Configuration with Pydantic Settings
  - `ntp_client.py`: Async NTP client
  - `consensus.py`: Consensus algorithm engine
  - `server.py`: MCP server with tools

### Infrastructure

- Python 3.11+ support
- CI/CD with GitHub Actions (Linux, macOS, Windows)
- Docker multi-stage build
- Fly.io deployment ready
- PyPI publishing workflow
- Automated changelog generation

[1.0.0]: https://github.com/chuk-ai/chuk-mcp-time/releases/tag/v1.0.0
