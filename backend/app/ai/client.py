"""
AI Client — Kimi (Moonshot) chat completions for sentiment and optimization helpers.
AI is an optional layer — all calls return None on failure.
"""

import json
import re

from loguru import logger

MODEL = "kimi-thinking"


class AIClient:
    """AI client using Moonshot OpenAI-compatible API (MOONSHOT_API_KEY)."""

    async def complete_async(self, system_prompt: str, user_prompt: str, max_tokens: int = 256) -> str | None:
        try:
            from mcp_server.kimi_client import kimi_complete

            return await kimi_complete(user_prompt, system_prompt, model=MODEL, max_tokens=max_tokens)
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return None

    async def complete_json_async(self, system_prompt: str, user_prompt: str, max_tokens: int = 256) -> dict | None:
        text = await self.complete_async(system_prompt, user_prompt, max_tokens)
        if text is None:
            return None
        try:
            cleaned = text.strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"AI JSON parse failed: {e}\nRaw: {text[:200]}")
            return None
