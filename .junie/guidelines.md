Project development guidelines for yfinance-mcp-server

Audience: Advanced contributors familiar with Python, uv, pytest, and MCP (Model Context Protocol).

1) Build and configuration
- Python/Runtime
  - Python >= 3.13 (enforced via pyproject.toml)
  - Package manager: uv (preferred). A uv.lock is present for reproducible installs.
  - Network access is required at runtime for yfinance calls (tests are written to avoid the network via mocking).

- Dependency install (using uv)
  - Install uv following upstream docs.
  - Sync: uv sync
  - Run commands in the project venv: uv run <cmd>
  - Example: uv run python -V and uv run pytest -q

- Alternative (system venv)
  - python -m venv .venv && source .venv/bin/activate
  - python -m pip install -U pip
  - pip install -e .  (optional; editable install not required)
  - pip install -r <generated> is not used; rely on pyproject deps instead: pip install . or pip install -e .
  - Note: The project expects dependencies from pyproject.toml (mcp[cli], yfinance, loguru, pytest).

- Running the MCP server
  - Primary entry point: stock_price_server.py (FastMCP via mcp.run()).
  - Run locally (stdio transport):
    - uv run python stock_price_server.py
    - Or: python stock_price_server.py
  - The server name is "Stock Price Server". Tools are auto-registered via @mcp.tool decorators.
  - Integration: Connect from an MCP-compatible client over stdio. No sockets/HTTP exposed by default.

- Docker
  - Build: docker build -t yfinance-mcp-server .
  - Run: docker run --rm yfinance-mcp-server
  - Container uses the same entry point. Ensure the container has Internet access if you intend to call yfinance-dependent tools.

2) Testing information
- Test runner: pytest (declared in pyproject). No additional plugins required.
- Current tests: tests/test_list_stock_symbols.py validates list_stock_symbols using unittest.mock to isolate from the network and yfinance service.
- Guiding principles:
  - Avoid live network in tests. Mock yfinance (e.g., patch("yfinance.search", ...)).
  - Keep tests deterministic and fast; assert only on public behavior.
  - For data frames/CSV produced by get_stock_history, prefer using small fixture data or patching yfinance.Ticker(...).history to return a controlled pandas DataFrame if you add such tests.

- How to run
  - Fast: uv run pytest -q
  - System Python: pytest -q
  - To run a single test file: pytest -q tests/test_list_stock_symbols.py
  - To increase verbosity or show print/logs: pytest -q -vv -s

- Adding tests (pattern)
  - Place files under tests/ named test_*.py or *_test.py.
  - Use unittest.mock.patch to isolate external calls:
    - from unittest.mock import patch
    - with patch("yfinance.search", return_value={"quotes": [{"symbol": "AAPL"}]}):
        assert list_stock_symbols("aap", 1) == ["AAPL"]
  - Example unit targets that do not require network:
    - list_tools(): returns a static, formatted description of available tools.
    - list_stock_symbols(): when yfinance.search is patched.
    - compare_stocks()/get_stock_price(): patch yfinance.Ticker(...).history and .info as appropriate.

- Demonstrated, verified workflow (performed before writing this file):
  1) Baseline: pytest -q → 3 passed.
  2) Add a temporary demo test tests/test_smoke_demo.py:
     - Content:
       import stock_price_server as sps
       def test_list_tools_contains_expected_entries():
           output = sps.list_tools()
           assert "Available tools in Stock Price Server:" in output
           assert "get_stock_price" in output
           assert "list_stock_symbols" in output
  3) Run: pytest -q → 4 passed.
  4) Remove the temporary file to keep the repo clean: rm -f tests/test_smoke_demo.py
  5) Final check: pytest -q → 3 passed.
  These commands were executed successfully during this update.

- Writing new tests for history/price without network
  - Example for get_stock_price:
    from unittest.mock import patch, MagicMock
    import pandas as pd
    import stock_price_server as sps
    def test_get_stock_price_uses_close():
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({"Close": [123.45]})
        with patch("yfinance.Ticker", return_value=mock_ticker):
            assert sps.get_stock_price("AAPL") == 123.45
  - Example for fallback to info:
    def test_get_stock_price_fallback_to_info():
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {"regularMarketPrice": 101.0}
        with patch("yfinance.Ticker", return_value=mock_ticker):
            assert sps.get_stock_price("AAPL") == 101.0

- CI considerations
  - Keep tests offline-compatible. If adding any integration tests requiring Internet, mark them and skip by default (e.g., @pytest.mark.integration and skip unless an env flag is set).

3) Additional development information
- Code style and typing
  - Follow PEP 8. The code uses type hints (e.g., -> float, -> list[str]). Prefer explicit types for public functions/tools.
  - Keep tool docstrings up to date; these double as user-facing help for MCP clients.

- Logging
  - Centralized via utils/LoggerSingleton.py using loguru. Logs are written under logs/YYYY-MM-DD.log and auto-rotate per Loguru defaults if configured.
  - Known cosmetic issue: logger is initialized with name "dice-mcp-server"; consider aligning to project name for consistency in future changes.
  - When catching exceptions in tools, prefer logger.exception(...) to capture tracebacks while returning safe fallbacks to the MCP client.

- MCP/FastMCP specifics
  - @mcp.tool() registers functions as MCP tools. You can also register a resource-like tool by providing a URI template: @mcp.tool("stock://{symbol}").
  - The server runs over stdio; no additional configuration is required inside this repo. Client-side configuration depends on the MCP consumer.
  - Keep tool signatures JSON-serializable and return plain types or strings. Avoid returning complex objects unless serialized.

- yfinance considerations
  - yfinance.search returns a dict with a "quotes" list; items vary by symbol and locale. Always defensive-check keys and types.
  - Ticker.history(...) may return empty frames (e.g., after-hours/closed market, invalid symbol). The current implementation falls back to info["regularMarketPrice"].
  - Avoid tight polling or high-frequency calls; Yahoo endpoints can rate-limit. Batch or cache if you add higher-level features.
  - Timezones/market holidays can affect data availability; design user-facing messages accordingly.

- Extending tools
  - TODOs for high-priority tools are tracked in TODO.md (e.g., company info, financial statements, options chain info). Prefer adding tests with mocks around yfinance for each new tool.

- Reproducibility
  - Prefer uv to ensure dependency consistency via uv.lock. When bumping dependencies, run uv lock to update the lockfile and validate tests.

- Project boundaries
  - Keep additional artifacts out of VCS unless essential. For ad-hoc experiments, work under a temporary directory and clean up. Tests should remain under tests/.
