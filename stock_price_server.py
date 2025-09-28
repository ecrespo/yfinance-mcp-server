from mcp.server.fastmcp import FastMCP
import yfinance as yf
from utils.LoggerSingleton import logger

# Create an MCP server with a custom name
mcp = FastMCP("Stock Price Server")


@mcp.tool()
def get_stock_price(symbol: str) -> float:
    """
    Fetches the current stock price for the given symbol using the Yahoo Finance API.

    The function retrieves the most recent historical data from Yahoo Finance for the
    specified stock symbol. If the data for the current day is not available or if an
    error occurs, it attempts to retrieve the regular market price from the stock's
    information. In case of any failure, the function logs the exception and returns
    a default value of -1.0.

    :param symbol: The stock symbol to fetch the price for, given as a string.
    :type symbol: str
    :return: The current stock price as a floating-point number. If the price cannot
             be determined, returns -1.0.
    :rtype: float
    """
    try:
        ticker = yf.Ticker(symbol)
        # Get today's historical data; may return empty if market is closed or symbol is invalid.
        data = ticker.history(period="1d")
        if not data.empty:
            # Use the last closing price from today's data
            price = data['Close'].iloc[-1]
            return float(price)

        # As a fallback, try using the regular market price from the ticker info
        info = ticker.info
        price = info.get("regularMarketPrice", None)
        return float(price) if price is not None else -1.0
    except Exception:
        # Return -1.0 to indicate an error occurred when fetching the stock price
        logger.exception("Error retrieving stock price")
        return -1.0


@mcp.tool("stock://{symbol}")
def stock_resource(symbol: str) -> str:
    """
    Retrieves the current stock price for a given stock symbol.

    This function fetches the latest stock price for the specified stock symbol.
    If the price is successfully retrieved, it returns the formatted price as a string.
    In cases where the price cannot be retrieved (e.g., an invalid symbol or other
    errors), an error message will be logged and returned.

    :param symbol: The stock symbol to retrieve the price for.
    :type symbol: str
    :return: A formatted string with the stock price or an error message if retrieval fails.
    :rtype: str
    """
    price = get_stock_price(symbol)
    if price < 0:
        logger.error(f"Error: Could not retrieve price for symbol '{symbol}'.")
        return f"Error: Could not retrieve price for symbol '{symbol}'."

    return f"The current price of '{symbol}' is ${price:.2f}."


@mcp.tool()
def get_stock_history(symbol: str, period: str = "1mo") -> str:
    """
    Fetches historical stock data for a given symbol and period.

    This function uses the yfinance library to retrieve historical market data
    for a specified stock symbol over a defined period. The data is returned
    in CSV format. If no data is found, a corresponding message is returned.

    :param symbol: The stock symbol for which historical data is to be retrieved.
    :type symbol: str
    :param period: The period for which historical data is requested. Defaults to "1mo".
    :type period: str
    :return: A string containing the historical data in CSV format or a message
             indicating no data or an error occurred.
    :rtype: str
    """
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        if data.empty:
            return f"No historical data found for symbol '{symbol}' with period '{period}'."
        # Convert the DataFrame to a CSV formatted string
        csv_data = data.to_csv()
        return csv_data
    except Exception as e:
        logger.exception(f"Error retrieving historical data for symbol '{symbol}'.")
        return f"Error fetching historical data: {str(e)}"


@mcp.tool()
def compare_stocks(symbol1: str, symbol2: str) -> str:
    """
    Compares the current stock prices of two given stock symbols.

    This function retrieves the stock prices for the two provided stock symbols and
    compares their values. If the price of the first stock is higher, lower, or equal
    to the price of the second stock, it returns a message indicating the result of
    the comparison. If the price data cannot be retrieved for either of the stocks,
    an error message is returned.

    :param symbol1: The stock symbol of the first company to compare.
    :type symbol1: str
    :param symbol2: The stock symbol of the second company to compare.
    :type symbol2: str
    :return: A string message indicating the comparison result or an error
        message if data retrieval fails.
    :rtype: str
    """
    price1 = get_stock_price(symbol1)
    price2 = get_stock_price(symbol2)
    if price1 < 0 or price2 < 0:
        return f"Error: Could not retrieve data for comparison of '{symbol1}' and '{symbol2}'."
    if price1 > price2:
        result = f"{symbol1} (${price1:.2f}) is higher than {symbol2} (${price2:.2f})."
    elif price1 < price2:
        result = f"{symbol1} (${price1:.2f}) is lower than {symbol2} (${price2:.2f})."
    else:
        result = f"Both {symbol1} and {symbol2} have the same price (${price1:.2f})."
    return result

@mcp.tool()
def list_tools() -> str:
    """
        Lists all available tools in this MCP server.

        This function provides an overview of all the tools available in the stock price
        server, including their names and descriptions. This is useful for understanding
        what functionality is available without having to inspect the source code.

        :return: A formatted string containing the names and descriptions of all available tools.
        :rtype: str
    """
    tools_info = [
        "Available tools in Stock Price Server:",
        "",
        "1. get_stock_price(symbol: str) -> float",
        "   Fetches the current stock price for the given symbol using Yahoo Finance API.",
        "",
        "2. stock_resource(symbol: str) -> str",
        "   Retrieves the current stock price for a given stock symbol (formatted output).",
        "",
        "3. get_stock_history(symbol: str, period: str = '1mo') -> str",
        "   Fetches historical stock data for a given symbol and period in CSV format.",
        "",
        "4. compare_stocks(symbol1: str, symbol2: str) -> str",
        "   Compares the current stock prices of two given stock symbols.",
        "",
        "5. list_tools() -> str",
        "   Lists all available tools in this MCP server (this tool).",
    ]

    return "\n".join(tools_info)





if __name__ == "__main__":
    mcp.run()

