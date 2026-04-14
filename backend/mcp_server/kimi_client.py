"""
Kimi (Moonshot) agent loop — OpenAI-compatible chat completions + tool calling.

Used when the decision model is a Kimi model (e.g. kimi-thinking). Requires
MOONSHOT_API_KEY and optionally MOONSHOT_API_BASE (default https://api.moonshot.ai/v1).
Dispatches tools to the same Python modules as the MCP server (see kimi_tool_dispatch.py).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from loguru import logger

from app.config import settings
from mcp_server.kimi_tool_dispatch import OPENAI_TOOL_SPECS_ALL, SPECS_BY_NAME, dispatch_mcp_tool_json


def normalize_kimi_model(model: str) -> str:
    """Map friendly aliases to Moonshot API model IDs."""
    m = model.strip()
    if m == "kimi-thinking":
        return "kimi-k2-thinking"
    return m


async def kimi_complete(
    user_prompt: str,
    system_prompt: str,
    model: str = "kimi-thinking",
    max_tokens: int = 256,
    timeout: int = 60,
) -> str | None:
    """Simple prompt → text via Moonshot chat completions (no tools)."""
    api_key = (settings.moonshot_api_key or os.environ.get("MOONSHOT_API_KEY", "")).strip()
    base = (settings.moonshot_api_base or os.environ.get("MOONSHOT_API_BASE", "https://api.moonshot.ai/v1")).rstrip(
        "/"
    )
    model_id = normalize_kimi_model(model)
    if not api_key:
        logger.warning("kimi_complete: MOONSHOT_API_KEY not set")
        return None
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            logger.error(f"kimi_complete HTTP {resp.status_code}: {(resp.text or '')[:300]}")
            return None
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            logger.info(f"kimi_complete: {len(content)} chars")
            return content
        return None
    except Exception as e:
        logger.error(f"kimi_complete error: {e}")
        return None


def _filter_tools(allowed: list[str] | None) -> list[dict[str, Any]]:
    """Orchestrator passes a subset; single-agent uses the full MCP tool surface."""
    if allowed is None:
        return list(OPENAI_TOOL_SPECS_ALL)
    return [SPECS_BY_NAME[name] for name in allowed if name in SPECS_BY_NAME]


async def kimi_agent_loop(
    prompt: str,
    system_prompt: str,
    model: str = "kimi-thinking",
    allowed_tools: list[str] | None = None,
    max_turns: int = 15,
    timeout: int = 120,
) -> dict[str, Any]:
    """Multi-turn agent loop with Kimi chat completions + local tool execution."""
    start_time = time.time()
    api_key = (settings.moonshot_api_key or os.environ.get("MOONSHOT_API_KEY", "")).strip()
    base = (settings.moonshot_api_base or os.environ.get("MOONSHOT_API_BASE", "https://api.moonshot.ai/v1")).rstrip(
        "/"
    )
    model_id = normalize_kimi_model(model)

    text_parts: list[str] = []
    tool_calls: list[dict] = []
    turns = 0

    if not api_key:
        return {
            "response": "Agent error: MOONSHOT_API_KEY is not set",
            "tool_calls": [],
            "turns": 0,
            "duration_s": round(time.time() - start_time, 1),
            "error": "MOONSHOT_API_KEY missing",
        }

    tools = _filter_tools(allowed_tools)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            for _ in range(max_turns):
                if time.time() - start_time > timeout:
                    logger.warning(f"Kimi agent timeout after {timeout}s")
                    break

                payload: dict[str, Any] = {
                    "model": model_id,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                }

                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    err_text = resp.text[:500]
                    logger.error(f"Kimi API error {resp.status_code}: {err_text}")
                    return {
                        "response": f"Agent error: Kimi API {resp.status_code}: {err_text}",
                        "tool_calls": tool_calls,
                        "turns": turns,
                        "duration_s": round(time.time() - start_time, 1),
                        "error": err_text,
                    }

                data = resp.json()
                choice = (data.get("choices") or [{}])[0]
                msg = choice.get("message") or {}
                turns += 1

                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    text_parts.append(content)

                raw_tool_calls = msg.get("tool_calls") or []

                if not raw_tool_calls:
                    break

                messages.append(msg)

                for tc in raw_tool_calls:
                    fn = tc.get("function") or {}
                    tname = fn.get("name") or ""
                    tid = tc.get("id") or ""
                    args = fn.get("arguments") or "{}"
                    tool_calls.append({"tool": tname, "input": args})
                    logger.info(f"[Kimi] Tool: {tname}")
                    arg_str = args if isinstance(args, str) else json.dumps(args)
                    result_str = await dispatch_mcp_tool_json(tname, arg_str)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tid,
                            "content": result_str,
                        }
                    )

            duration = round(time.time() - start_time, 1)
            response = "".join(text_parts) or "No response"
            logger.info(f"Kimi agent: {turns} turns, {len(tool_calls)} tools, {duration}s")

            return {
                "response": response,
                "tool_calls": tool_calls,
                "turns": turns,
                "duration_s": duration,
                "cost_usd": None,
            }

    except Exception as e:
        logger.error(f"Kimi agent error: {e}")
        return {
            "response": f"Agent error: {e}",
            "tool_calls": tool_calls,
            "turns": turns,
            "duration_s": round(time.time() - start_time, 1),
            "error": str(e),
        }
