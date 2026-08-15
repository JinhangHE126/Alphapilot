"""Global AI output and publication kill switches."""
from __future__ import annotations

import os

ENV_OUTPUT = "AI_OUTPUT_ENABLED"
ENV_PUBLICATION = "AI_PUBLICATION_ENABLED"


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def is_output_enabled() -> bool:
    """Whether model-generated output is currently allowed."""
    return _env_bool(ENV_OUTPUT, default=True)


def is_publication_enabled() -> bool:
    """Whether approved reports are currently allowed to be published."""
    return _env_bool(ENV_PUBLICATION, default=True)


def current_kill_switch_status() -> str:
    """
    Operational status used by audit records.

    - enabled: output and publication both enabled
    - output_paused: output disabled
    - publication_paused: publication disabled
    - output_and_publication_paused: both disabled
    """
    output_ok = is_output_enabled()
    pub_ok = is_publication_enabled()
    if output_ok and pub_ok:
        return "enabled"
    if (not output_ok) and (not pub_ok):
        return "output_and_publication_paused"
    if not output_ok:
        return "output_paused"
    return "publication_paused"


__all__ = [
    "ENV_OUTPUT",
    "ENV_PUBLICATION",
    "is_output_enabled",
    "is_publication_enabled",
    "current_kill_switch_status",
]
