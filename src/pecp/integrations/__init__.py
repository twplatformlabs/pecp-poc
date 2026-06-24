"""PECP integration hook registry and dispatcher (INTG-01, INTG-02, INTG-03)."""

import logging
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from pecp.integrations.base import IntegrationBase

logger = logging.getLogger(__name__)

INTEGRATION_REGISTRY: list[IntegrationBase] = []


async def fire_integrations(hook_name: str, *args: Any) -> None:
    """Fire all registered integrations for the named lifecycle hook.

    Errors in individual integrations are caught and logged — they never
    propagate to the caller (INTG-02). Fired in INTEGRATION_REGISTRY order.
    """
    for integration in INTEGRATION_REGISTRY:
        hook = getattr(integration, hook_name, None)
        if hook is not None:
            try:
                await hook(*args)
            except Exception:
                logger.warning(
                    "Integration hook %s.%s failed",
                    type(integration).__name__,
                    hook_name,
                    exc_info=True,
                )


class IntegrationConfig(BaseSettings):
    """Integration environment configuration via pydantic-settings (INTG-03).

    Reads GITHUB_PAT and GITHUB_ORG from the environment.
    Both default to empty strings so missing env vars do not crash the server.
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    GITHUB_PAT: str = ""
    GITHUB_ORG: str = ""


def load_and_register_integrations() -> None:
    """Load integration config and populate INTEGRATION_REGISTRY.

    Called from FastAPI lifespan. Missing config logs a warning and
    skips registration — server starts normally (INTG-03).
    """
    cfg = IntegrationConfig()
    if not cfg.GITHUB_PAT or not cfg.GITHUB_ORG:
        logger.warning(
            "GITHUB_PAT or GITHUB_ORG not set — GitHub integration disabled"
        )
        return

    # Phase 8: INTEGRATION_REGISTRY.append(GitHubIntegration(cfg))
