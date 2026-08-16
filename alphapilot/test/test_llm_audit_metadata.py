"""Unit tests for analysis model/prompt audit metadata."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.llm import get_analysis_audit_metadata  # noqa: E402


def test_get_analysis_audit_metadata_returns_non_empty_routing_snapshot(monkeypatch):
    monkeypatch.delenv("PROMPT_VERSION", raising=False)
    monkeypatch.delenv("MODEL_VERSION", raising=False)

    meta = get_analysis_audit_metadata()

    assert meta["model_provider"]
    assert meta["model_name"]
    assert meta["model_version"] == "provider-managed"
    assert meta["prompt_version"] == "alphapilot-prompts-v1"
    assert "deepseek" in meta["model_name"] or "gemini" in meta["model_name"] or "grok" in meta["model_name"]


def test_get_analysis_audit_metadata_respects_env_overrides(monkeypatch):
    monkeypatch.setenv("PROMPT_VERSION", "alphapilot-prompts-v9")
    monkeypatch.setenv("MODEL_VERSION", "demo-model-bundle-1")

    meta = get_analysis_audit_metadata()

    assert meta["prompt_version"] == "alphapilot-prompts-v9"
    assert meta["model_version"] == "demo-model-bundle-1"
