"""
Kimi tool schemas + dispatch — mirrors mcp_server/server.py tool routing.

Used when Kimi runs with the full single-agent tool surface (allowed_tools=None).
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from mcp_server.tools import (
    broker,
    history,
    indicators,
    journal,
    learning,
    market_data,
    portfolio,
    risk,
    sentiment,
    session,
    strategy_gen,
)


def _spec(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


# OpenAI-style tool list matching MCP server tools (server.py)
OPENAI_TOOL_SPECS_ALL: list[dict[str, Any]] = [
    _spec("get_tick", "Get current bid/ask tick for a symbol.", {"symbol": {"type": "string"}}, ["symbol"]),
    _spec(
        "get_ohlcv",
        "Get OHLCV candles.",
        {
            "symbol": {"type": "string"},
            "timeframe": {"type": "string"},
            "count": {"type": "integer"},
        },
        ["symbol"],
    ),
    _spec("get_spread", "Get current spread.", {"symbol": {"type": "string"}}, ["symbol"]),
    _spec(
        "calculate_ema",
        "Calculate EMA.",
        {
            "symbol": {"type": "string"},
            "period": {"type": "integer"},
            "timeframe": {"type": "string"},
        },
        ["symbol"],
    ),
    _spec(
        "calculate_rsi",
        "Calculate RSI.",
        {
            "symbol": {"type": "string"},
            "period": {"type": "integer"},
            "timeframe": {"type": "string"},
        },
        ["symbol"],
    ),
    _spec(
        "calculate_atr",
        "Calculate ATR.",
        {
            "symbol": {"type": "string"},
            "period": {"type": "integer"},
            "timeframe": {"type": "string"},
        },
        ["symbol"],
    ),
    _spec(
        "run_full_analysis",
        "Run full technical analysis bundle.",
        {"symbol": {"type": "string"}, "timeframe": {"type": "string"}},
        ["symbol"],
    ),
    _spec(
        "validate_trade",
        "Check trade vs risk rules.",
        {
            "symbol": {"type": "string"},
            "signal": {"type": "integer"},
            "current_positions": {"type": "integer"},
            "daily_pnl": {"type": "number"},
            "balance": {"type": "number"},
        },
        ["symbol", "signal", "current_positions", "daily_pnl", "balance"],
    ),
    _spec(
        "calculate_lot_size",
        "Calculate lot size.",
        {"symbol": {"type": "string"}, "balance": {"type": "number"}, "sl_pips": {"type": "number"}},
        ["symbol", "balance", "sl_pips"],
    ),
    _spec(
        "calculate_sl_tp",
        "Calculate SL/TP levels.",
        {
            "symbol": {"type": "string"},
            "entry_price": {"type": "number"},
            "signal": {"type": "integer"},
            "atr": {"type": "number"},
        },
        ["symbol", "entry_price", "signal", "atr"],
    ),
    _spec(
        "place_order",
        "Place order (guardrail-gated). order_type BUY or SELL.",
        {
            "symbol": {"type": "string"},
            "order_type": {"type": "string", "enum": ["BUY", "SELL"]},
            "lot": {"type": "number"},
            "sl": {"type": "number"},
            "tp": {"type": "number"},
            "comment": {"type": "string"},
        },
        ["symbol", "order_type", "lot", "sl", "tp"],
    ),
    _spec(
        "modify_position",
        "Modify SL/TP by ticket.",
        {
            "ticket": {"type": "integer"},
            "sl": {"type": "number"},
            "tp": {"type": "number"},
        },
        ["ticket"],
    ),
    _spec("close_position", "Close position by ticket.", {"ticket": {"type": "integer"}}, ["ticket"]),
    _spec(
        "get_positions",
        "List open positions.",
        {"symbol": {"type": "string"}},
        [],
    ),
    _spec("get_account", "Account summary.", {}, []),
    _spec("get_exposure", "Portfolio exposure.", {}, []),
    _spec(
        "check_correlation",
        "Check correlation conflicts.",
        {
            "symbol": {"type": "string"},
            "signal": {"type": "integer"},
            "active_positions": {"type": "object"},
        },
        ["symbol", "signal", "active_positions"],
    ),
    _spec("get_sentiment", "Latest sentiment.", {}, []),
    _spec("get_sentiment_history", "Sentiment history.", {"days": {"type": "integer"}}, []),
    _spec(
        "get_trade_history",
        "Trade history.",
        {"days": {"type": "integer"}, "symbol": {"type": "string"}},
        [],
    ),
    _spec("get_daily_pnl", "Daily PnL.", {"symbol": {"type": "string"}}, []),
    _spec(
        "get_performance",
        "Performance stats.",
        {"days": {"type": "integer"}, "symbol": {"type": "string"}},
        [],
    ),
    _spec(
        "log_decision",
        "Log trading decision.",
        {
            "symbol": {"type": "string"},
            "decision": {"type": "string"},
            "reasoning": {"type": "string"},
            "confidence": {"type": "number"},
        },
        ["symbol", "decision", "reasoning"],
    ),
    _spec("log_reasoning", "Log reasoning.", {"thought_process": {"type": "string"}}, ["thought_process"]),
    _spec(
        "analyze_recent_trades",
        "Analyze recent trades.",
        {"days": {"type": "integer"}, "symbol": {"type": "string"}},
        [],
    ),
    _spec(
        "detect_regime",
        "Detect market regime.",
        {"symbol": {"type": "string"}, "timeframe": {"type": "string"}},
        [],
    ),
    _spec("get_optimization_history", "Optimization history.", {"limit": {"type": "integer"}}, []),
    _spec(
        "save_context",
        "Save session context.",
        {"symbol": {"type": "string"}, "context": {"type": "object"}},
        ["symbol", "context"],
    ),
    _spec("get_context", "Get session context.", {"symbol": {"type": "string"}}, ["symbol"]),
    _spec(
        "save_learning",
        "Save cross-session learning.",
        {"learning_text": {"type": "string"}, "category": {"type": "string"}},
        ["learning_text"],
    ),
    _spec("get_learnings", "Get learnings.", {"category": {"type": "string"}}, []),
    _spec("get_strategy_profiles", "Strategy profiles.", {}, []),
    _spec(
        "recommend_strategy",
        "Recommend strategy for regime.",
        {"regime": {"type": "string"}, "symbol": {"type": "string"}},
        ["regime"],
    ),
    _spec(
        "generate_strategy_config",
        "Generate strategy config.",
        {
            "base_strategy": {"type": "string"},
            "param_overrides": {"type": "object"},
            "name": {"type": "string"},
        },
        ["base_strategy"],
    ),
    _spec(
        "generate_ensemble_config",
        "Generate ensemble config.",
        {"weights": {"type": "object"}, "name": {"type": "string"}},
        ["weights"],
    ),
]

SPECS_BY_NAME: dict[str, dict[str, Any]] = {s["function"]["name"]: s for s in OPENAI_TOOL_SPECS_ALL}


async def dispatch_mcp_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Route tool name + args to the same implementations as MCP server.py."""
    try:
        if name == "get_tick":
            return await market_data.get_tick(args["symbol"])
        if name == "get_ohlcv":
            return await market_data.get_ohlcv(
                args["symbol"],
                str(args.get("timeframe") or "M15"),
                int(args.get("count") or 100),
            )
        if name == "get_spread":
            return await market_data.get_spread(args["symbol"])
        if name == "calculate_ema":
            return await indicators.calculate_ema(
                args["symbol"],
                int(args.get("period") or 20),
                str(args.get("timeframe") or "M15"),
            )
        if name == "calculate_rsi":
            return await indicators.calculate_rsi(
                args["symbol"],
                int(args.get("period") or 14),
                str(args.get("timeframe") or "M15"),
            )
        if name == "calculate_atr":
            return await indicators.calculate_atr(
                args["symbol"],
                int(args.get("period") or 14),
                str(args.get("timeframe") or "M15"),
            )
        if name == "run_full_analysis":
            return await indicators.full_analysis(args["symbol"], str(args.get("timeframe") or "M15"))
        if name == "validate_trade":
            return risk.validate_trade(
                args["symbol"],
                int(args["signal"]),
                int(args["current_positions"]),
                float(args["daily_pnl"]),
                float(args["balance"]),
            )
        if name == "calculate_lot_size":
            return risk.calculate_lot(args["symbol"], float(args["balance"]), float(args["sl_pips"]))
        if name == "calculate_sl_tp":
            return risk.calculate_sl_tp(
                args["symbol"],
                float(args["entry_price"]),
                int(args["signal"]),
                float(args["atr"]),
            )
        if name == "place_order":
            return await broker.place_order(
                args["symbol"],
                args["order_type"],
                float(args["lot"]),
                float(args["sl"]),
                float(args["tp"]),
                str(args.get("comment") or ""),
            )
        if name == "modify_position":
            mp: dict[str, Any] = {"ticket": int(args["ticket"])}
            if "sl" in args:
                mp["sl"] = args["sl"]
            if "tp" in args:
                mp["tp"] = args["tp"]
            return await broker.modify_position(**mp)
        if name == "close_position":
            return await broker.close_position(int(args["ticket"]))
        if name == "get_positions":
            sym = args.get("symbol")
            return await broker.get_positions(sym if sym else None)
        if name == "get_account":
            return await portfolio.get_account()
        if name == "get_exposure":
            return await portfolio.get_exposure()
        if name == "check_correlation":
            return portfolio.check_correlation(args["symbol"], int(args["signal"]), args["active_positions"])
        if name == "get_sentiment":
            return await sentiment.get_latest_sentiment()
        if name == "get_sentiment_history":
            return await sentiment.get_sentiment_history(int(args.get("days") or 7))
        if name == "get_trade_history":
            return await history.get_trade_history(
                int(args.get("days") or 7),
                args.get("symbol"),
            )
        if name == "get_daily_pnl":
            return await history.get_daily_pnl(args.get("symbol"))
        if name == "get_performance":
            return await history.get_performance(int(args.get("days") or 30), args.get("symbol"))
        if name == "log_decision":
            ld: dict[str, Any] = {
                "symbol": args["symbol"],
                "decision": args["decision"],
                "reasoning": args["reasoning"],
            }
            if "confidence" in args and args["confidence"] is not None:
                ld["confidence"] = float(args["confidence"])
            return await journal.log_decision(**ld)
        if name == "log_reasoning":
            return await journal.log_reasoning(args["thought_process"])
        if name == "analyze_recent_trades":
            return await learning.analyze_recent_trades(int(args.get("days") or 7), args.get("symbol"))
        if name == "detect_regime":
            return await learning.detect_regime(str(args.get("symbol") or "GOLD"), str(args.get("timeframe") or "M15"))
        if name == "get_optimization_history":
            return await learning.get_optimization_history(int(args.get("limit") or 5))
        if name == "save_context":
            return await session.save_context(args["symbol"], args["context"])
        if name == "get_context":
            return await session.get_context(args["symbol"])
        if name == "save_learning":
            return await session.save_learning(
                str(args["learning_text"]),
                str(args.get("category") or "general"),
            )
        if name == "get_learnings":
            return await session.get_learnings(args.get("category"))
        if name == "get_strategy_profiles":
            return strategy_gen.get_strategy_profiles()
        if name == "recommend_strategy":
            return strategy_gen.recommend_strategy(args["regime"], str(args.get("symbol") or "GOLD"))
        if name == "generate_strategy_config":
            return strategy_gen.generate_strategy_config(
                args["base_strategy"],
                args.get("param_overrides"),
                args.get("name"),
            )
        if name == "generate_ensemble_config":
            return strategy_gen.generate_ensemble_config(args["weights"], str(args.get("name") or "custom_ensemble"))
    except Exception as e:
        logger.exception(f"Kimi dispatch error for {name}")
        return {"error": str(e)}

    return {"error": f"Unknown tool: {name}"}


async def dispatch_mcp_tool_json(name: str, arguments_json: str) -> str:
    try:
        args: dict[str, Any] = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid tool arguments JSON: {e}"})
    out = await dispatch_mcp_tool(name, args)
    return json.dumps(out, default=str)
