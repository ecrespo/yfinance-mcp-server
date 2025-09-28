import builtins
from unittest.mock import patch
import pytest

# Import the module under test
import stock_price_server as sps


class TestListStockSymbols:
    def test_returns_top_symbols_from_search(self):
        # Arrange: mock yfinance.search to return predictable data
        fake_response = {
            "quotes": [
                {"symbol": "AAPL", "shortname": "Apple Inc."},
                {"symbol": "AAP", "shortname": "Advance Auto Parts"},
                {"symbol": "AAPB", "shortname": "GraniteShares 2x Long AAPL"},
                {"symbol": "XYZ", "shortname": "Other"},
            ]
        }
        with patch("yfinance.search", return_value=fake_response) as mock_search:
            # Act
            result = sps.list_stock_symbols("aap", limit=3)

            # Assert
            mock_search.assert_called_once_with("aap")
            assert result == ["AAPL", "AAP", "AAPB"]

    def test_handles_empty_or_missing_quotes(self):
        with patch("yfinance.search", return_value={"quotes": []}):
            assert sps.list_stock_symbols("nosuch", limit=5) == []
        with patch("yfinance.search", return_value={}):
            assert sps.list_stock_symbols("nosuch", limit=5) == []

    def test_handles_exception_and_returns_empty_list(self):
        with patch("yfinance.search", side_effect=Exception("network error")):
            result = sps.list_stock_symbols("apple", limit=2)
            assert result == []
