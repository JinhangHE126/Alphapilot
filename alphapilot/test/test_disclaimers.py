"""Unit tests for centralized AI research disclaimers."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from governance.disclaimers import (  # noqa: E402
    DISCLAIMER_VERSION,
    attach_disclaimer_fields,
    get_ai_disclaimer,
    get_disclaimer_payload,
    normalize_disclaimer_language,
)


def test_normalize_disclaimer_language_maps_common_tags():
    assert normalize_disclaimer_language("zh-CN") == "zh-Hans"
    assert normalize_disclaimer_language("zh-HK") == "yue"
    assert normalize_disclaimer_language("en-US") == "en"


def test_get_ai_disclaimer_returns_localized_non_certification_text():
    zh = get_ai_disclaimer("zh-Hans")
    en = get_ai_disclaimer("en")
    assert "不构成" in zh or "投资建议" in zh
    assert "investment advice" in en.lower()
    assert "SFC" in zh and "SFC" in en
    assert "certification" in en.lower() or "认证" in zh


def test_attach_disclaimer_fields_preserves_payload_and_version():
    payload = attach_disclaimer_fields({"report": "ok"}, "en")
    assert payload["report"] == "ok"
    assert payload["disclaimer_version"] == DISCLAIMER_VERSION
    assert payload["disclaimer"] == get_disclaimer_payload("en")["disclaimer"]
