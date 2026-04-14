"""
Base agent — shared agent loop using Kimi (Moonshot) OpenAI-compatible API.

All agents (specialists, orchestrator, single-agent) use the same Moonshot stack.
"""

from typing import Any

from mcp_server.kimi_client import kimi_agent_loop


# ─── Model Constants ─────────────────────────────────────────────────────────

MODEL_ORCHESTRATOR = "kimi-thinking"
MODEL_SPECIALIST = "kimi-thinking"


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
    """Run an agent loop with Kimi chat completions + tool dispatch.

    Args:
        system_prompt: Agent's system prompt
        user_message: The task/query
        tools: Legacy — ignored
        tool_names: Filter which tools are visible (orchestrator subset vs full single-agent)
        model: Kimi model id (default kimi-thinking)
        max_turns: Maximum turns
        timeout: Timeout in seconds

    Returns:
        Dict with response, tool_calls, turns, duration_s.
    """
    return await kimi_agent_loop(
        prompt=user_message,
        system_prompt=system_prompt,
        model=model,
        allowed_tools=tool_names,
        max_turns=max_turns,
        timeout=timeout,
    )
