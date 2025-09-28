# yfinance-mcp-server

A minimal MCP (Model Context Protocol) server that provides stock price data using Yahoo Finance via the `yfinance` library. It exposes tools to get the current price, fetch historical data, and compare two symbols.

## Overview
- Stack: Python 3.13, MCP (fastmcp), yfinance, loguru
- Package manager: uv (pyproject/uv.lock present)
- Entry point: `stock_price_server.py` (runs a FastMCP server with `mcp.run()`)
- Container support: Dockerfile provided
- Logging: Structured logs written to `logs/YYYY-MM-DD.log`

### Exposed MCP tools
Implemented in `stock_price_server.py`:
- `get_stock_price(symbol: str) -> float` — returns the current/most recent price.
- `stock_resource(symbol: str) -> str` — resource endpoint alias `stock://{symbol}` returning a formatted string.
- `get_stock_history(symbol: str, period: str = "1mo") -> str` — historical data in CSV format.
- `compare_stocks(symbol1: str, symbol2: str) -> str` — compares two symbols' current prices.
- `list_tools() -> str` — lists available tools.

## Requirements
- Python 3.13+
- uv (https://github.com/astral-sh/uv) — for dependency management
- Internet access for the process to query Yahoo Finance

Optional:
- Docker (if running in a container)

## Setup
Using uv:
1. Install uv (if not installed): follow the uv docs.
2. Sync dependencies:
   - `uv sync`

This will create a virtual environment at `.venv` and install dependencies from `pyproject.toml`/`uv.lock`.

## Run
Run directly with uv:
- `uv run python stock_price_server.py`

Run with system Python (if you prefer and have deps installed):
- `python3 stock_price_server.py`

Docker:
- Build: `docker build -t yfinance-mcp-server .`
- Run: `docker run --rm yfinance-mcp-server`

Notes:
- The MCP server communicates over stdio by default (as typical for MCP servers). Integrate with your MCP-compatible client accordingly.
- TODO: Add client-specific instructions (e.g., how to connect from particular editors/agents/CLI).

## Scripts
No custom scripts are defined in `pyproject.toml` at this time.
- TODO: Consider adding a console script entry point for easier invocation (e.g., `yfinance-mcp-server`).

## Environment variables
There are no required environment variables.
- Logging:
  - Logs are written to the `logs` directory by default (created automatically).
  - The logger name currently defaults to `dice-mcp-server` in `utils/LoggerSingleton.py` (a cosmetic label in logs). TODO: Align this name with the project.
- TODO: Add configurable log level/paths via env vars if needed.

## Tests
No tests are included yet.
- TODO: Add a basic test suite (e.g., with `pytest`) and CI.

## Project structure
```
.
├─ Dockerfile
├─ LICENSE
├─ README.md
├─ pyproject.toml
├─ uv.lock
├─ stock_price_server.py
└─ utils/
   ├─ __init__.py
   └─ LoggerSingleton.py
```

## Development notes
- Dependencies (from `pyproject.toml`):
  - `mcp[cli]` >= 1.15.0
  - `yfinance` >= 0.2.66
  - `loguru` >= 0.7.3
- Python version: `>=3.13`

## License
This project is licensed under the terms of the license in the `LICENSE` file.