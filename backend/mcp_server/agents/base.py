"""
Base agent — shared agent loop using Claude Agent SDK or Kimi (Moonshot) API.

Specialists use Claude (Haiku). Orchestrator / single-agent decision uses
MODEL_ORCHESTRATOR (Kimi kimi-thinking by default) or Claude when overridden.
"""

from typing import Any

from mcp_server.kimi_client import kimi_agent_loop
from mcp_server.sdk_client import sdk_agent_loop


# ─── Model Constants ─────────────────────────────────────────────────────────

MODEL_ORCHESTRATOR = "kimi-thinking"
MODEL_SPECIALIST = "claude-haiku-4-5-20251001"


def _is_kimi_decision_model(model: str) -> bool:
    """Kimi models use OpenAI-compatible Moonshot API (not Claude Agent SDK)."""
    return model.lower().startswith("kimi")


# ─── Shared Agent Loop ──────────────────────────────────────────────────────

async def run_agent_loop(
    system_prompt: str,
    user_message: str,
    tools: list[dict[str, Any]] | None = None,
    tool_names: list[str] | None = None,
    model: str = MODEL_SPECIALIST,
    max_turns: int = 15,
    timeout: int = 120,
    **kwargs,
) -> dict:
    """Run an agent loop: Claude Agent SDK, or Kimi chat completions + tool dispatch.

    Args:
        system_prompt: Agent's system prompt
        user_message: The task/query
        tools: Legacy — ignored (tools come from MCP or Kimi tool specs)
        tool_names: Filter which tools are visible (orchestrator execution set for Kimi)
        model: Claude or Kimi model id
        max_turns: Maximum turns
        timeout: Timeout in seconds

    Returns:
        Dict with response, tool_calls, turns, duration_s.
    """
    if _is_kimi_decision_model(model):
        return await kimi_agent_loop(
            prompt=user_message,
            system_prompt=system_prompt,
            model=model,
            allowed_tools=tool_names,
            max_turns=max_turns,
            timeout=timeout,
        )
    return await sdk_agent_loop(
        prompt=user_message,
        system_prompt=system_prompt,
        model=model,
        allowed_tools=tool_names,
        max_turns=max_turns,
        timeout=timeout,
    )
