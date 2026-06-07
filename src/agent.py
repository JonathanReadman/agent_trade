import json
import os
import anthropic
from src.news import get_news
from src.technicals import get_technicals
from src.portfolio import get_portfolio
from src.ledger import execute_trade
from src.db import DEFAULT_DB_PATH

STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))
MODEL = "claude-opus-4-8"


def build_tool_definitions() -> list:
    return [
        {
            "name": "get_news",
            "description": "Fetch recent news headlines for a stock ticker from the last 24 hours.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
                },
                "required": ["ticker"],
            },
        },
        {
            "name": "get_technicals",
            "description": "Fetch technical indicators for a stock: close price, volume, RSI, MACD, and 1-day price change %.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"],
            },
        },
        {
            "name": "get_portfolio",
            "description": "Get current paper portfolio state: cash balance, open holdings, total value.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "execute_trade",
            "description": (
                "Record a paper trade decision. Action must be BUY, SELL, or HOLD. "
                "Confidence is 0.0-1.0. Trades below 0.6 confidence are rejected. "
                "Position size is calculated automatically via Kelly criterion."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "signal_price": {"type": "number", "description": "Current price at time of decision"},
                    "reasoning": {"type": "string", "description": "Your full chain-of-thought reasoning for this decision"},
                },
                "required": ["ticker", "action", "confidence", "signal_price", "reasoning"],
            },
        },
    ]


def _dispatch_tool(tool_name: str, tool_input: dict, news_api_key: str,
                   db_path: str) -> str:
    if tool_name == "get_news":
        result = get_news(tool_input["ticker"], api_key=news_api_key)
        return json.dumps({"ticker": result.ticker, "headlines": result.headlines})

    if tool_name == "get_technicals":
        result = get_technicals(tool_input["ticker"])
        if result is None:
            return json.dumps({"error": "no data available"})
        return json.dumps({
            "ticker": result.ticker,
            "close_price": result.close_price,
            "volume": result.volume,
            "rsi": result.rsi,
            "macd": result.macd,
            "macd_signal": result.macd_signal,
            "price_change_pct": result.price_change_pct,
        })

    if tool_name == "get_portfolio":
        state = get_portfolio(db_path=db_path)
        return json.dumps({
            "cash_usd": state.cash_usd,
            "total_value_usd": state.total_value_usd,
            "holdings": state.holdings,
        })

    if tool_name == "execute_trade":
        result = execute_trade(
            ticker=tool_input["ticker"],
            action=tool_input["action"],
            confidence=tool_input["confidence"],
            signal_price=tool_input["signal_price"],
            reasoning=tool_input["reasoning"],
            db_path=db_path,
        )
        return json.dumps({
            "status": result.status,
            "position_size_usd": result.position_size_usd,
            "rejection_reason": result.rejection_reason,
        })

    return json.dumps({"error": f"unknown tool: {tool_name}"})


def run_agent_cycle(
    tickers: list,
    api_key: str,
    news_api_key: str,
    db_path: str = DEFAULT_DB_PATH,
) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    tools = build_tool_definitions()

    system_prompt = (
        "You are a disciplined paper trading agent. You analyze S&P 500 stocks using "
        "news sentiment and technical indicators, then make BUY, SELL, or HOLD decisions. "
        "For each ticker: (1) fetch news, (2) fetch technicals, (3) check portfolio, "
        "(4) reason carefully, (5) call execute_trade with your decision and a detailed reasoning string. "
        "Be conservative. Only trade with high conviction. Your reasoning text is logged for audit — "
        "explain your thinking clearly. Do not trade on weak or ambiguous signals."
    )

    user_message = (
        f"Please analyze the following S&P 500 tickers and make paper trading decisions for each: "
        f"{', '.join(tickers)}. "
        f"Work through each ticker systematically using your tools."
    )

    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            return " ".join(text_blocks) if text_blocks else "Cycle complete."

        if response.stop_reason != "tool_use":
            return f"Unexpected stop reason: {response.stop_reason}"

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_content = _dispatch_tool(
                    block.name, block.input, news_api_key, db_path
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_content,
                })

        messages.append({"role": "user", "content": tool_results})
