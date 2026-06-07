import pytest
from unittest.mock import patch, MagicMock
from src.agent import build_tool_definitions, run_agent_cycle

def test_build_tool_definitions_returns_four_tools():
    tools = build_tool_definitions()
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_news", "get_technicals", "get_portfolio", "execute_trade"}

def test_each_tool_has_required_fields():
    tools = build_tool_definitions()
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool

def test_run_agent_cycle_returns_summary(monkeypatch):
    mock_client = MagicMock()
    # Simulate Claude returning a final text message (no tool calls)
    mock_message = MagicMock()
    mock_message.stop_reason = "end_turn"
    mock_message.content = [MagicMock(type="text", text="Analysis complete. No strong signals today.")]
    mock_client.messages.create.return_value = mock_message

    with patch("src.agent.anthropic.Anthropic", return_value=mock_client):
        summary = run_agent_cycle(
            tickers=["AAPL"],
            api_key="test_key",
            news_api_key="test_news_key",
            db_path=":memory:",
        )

    assert isinstance(summary, str)
    assert len(summary) > 0
