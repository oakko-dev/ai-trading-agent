"""
API key health monitor — periodic checks on Moonshot (Kimi) API key validity.

If the key is invalid, the agent should pause or alert.
"""

from datetime import UTC, datetime

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Secret
from app.vault import vault


async def check_oauth_health(db: AsyncSession, notifier=None) -> dict:
    """Check Moonshot API key validity (stored under auth category in Vault).

    Called by BotScheduler every 5 minutes.
    Returns status dict: {status, message, latency_ms, checked_at}
    """
    if not vault.is_available:
        return {
            "status": "unavailable",
            "message": "Vault not configured",
            "checked_at": datetime.now(UTC).isoformat(),
        }

    result = await db.execute(
        select(Secret).where(
            Secret.category == "auth",
            Secret.is_deleted.is_(False),
        )
    )
    secret = result.scalar_one_or_none()
    if not secret:
        return {
            "status": "missing",
            "message": "No auth API key in vault",
            "checked_at": datetime.now(UTC).isoformat(),
        }

    try:
        token = vault.decrypt(secret.encrypted_value, secret.nonce)
    except Exception as e:
        logger.error(f"Vault health: failed to decrypt secret — {e}")
        return {
            "status": "error",
            "message": "Failed to decrypt secret",
            "checked_at": datetime.now(UTC).isoformat(),
        }

    base = (settings.moonshot_api_base or "https://api.moonshot.ai/v1").rstrip("/")
    start = datetime.now(UTC)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {token.strip()}"},
            )
        latency_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)

        if resp.status_code == 200:
            logger.debug(f"Vault health: Moonshot API key valid ({latency_ms}ms)")
            return {
                "status": "ok",
                "message": "API key valid",
                "latency_ms": latency_ms,
                "checked_at": datetime.now(UTC).isoformat(),
            }

        status_map = {
            401: ("invalid", "API key expired or revoked"),
            403: ("forbidden", "API key lacks required permissions"),
            429: ("rate_limited", "API rate limited"),
        }
        status, message = status_map.get(
            resp.status_code,
            ("error", f"Unexpected status: {resp.status_code}"),
        )

        logger.warning(f"Vault health: Moonshot API key {status} — {message}")

        if status in ("invalid", "forbidden") and notifier:
            await _send_alert(notifier, status, message)

        return {
            "status": status,
            "message": message,
            "latency_ms": latency_ms,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    except httpx.TimeoutException:
        logger.warning("Vault health: Moonshot API check timed out")
        return {
            "status": "timeout",
            "message": "API check timed out",
            "checked_at": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(f"Vault health: check failed — {e}")
        return {
            "status": "error",
            "message": str(e),
            "checked_at": datetime.now(UTC).isoformat(),
        }


async def _send_alert(notifier, status: str, message: str):
    """Send alert via Telegram."""
    try:
        alert_text = (
            f"🔴 Kimi API Key Alert\n"
            f"Status: {status}\n"
            f"Message: {message}\n"
            f"Action: Check Secrets Vault and rotate MOONSHOT_API_KEY if needed."
        )
        await notifier.send(alert_text)
    except Exception as e:
        logger.error(f"Vault health: failed to send alert — {e}")
