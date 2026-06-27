"""HKEX fetcher unit tests (network-light + optional live)."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.fetchers.hkex_fetcher import (
    _hkex_display_code,
    _parse_html_listings,
    _publish_date_from_url,
    resolve_hkex_stock_id,
)


SAMPLE_HTML = """
Release Time: 08/04/2025 18:20
Stock Code: 00700
Document: Financial Statements - [Annual Report] ANNUAL REPORT 2024
<a href="/listedco/listconews/sehk/2025/0408/2025040800667.pdf">PDF</a>
Release Time: 08/04/2024 18:10
Document: Financial Statements - [Annual Report] ANNUAL REPORT 2023
<a href="/listedco/listconews/sehk/2024/0408/2024040801822.pdf">PDF</a>
"""


def test_hkex_display_code():
    assert _hkex_display_code("0700.HK") == "00700"
    assert _hkex_display_code("700.HK") == "00700"
    assert _hkex_display_code("00700.HK") == "00700"


def test_publish_date_from_url():
    assert _publish_date_from_url(
        "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0408/2025040800667.pdf"
    ) == "2025-04-08"


def test_parse_html_listings():
    items = _parse_html_listings(SAMPLE_HTML)
    assert len(items) == 2
    assert "ANNUAL REPORT 2024" in items[0]["title"]
    assert items[0]["publish_date"] == "2025-04-08"
    assert items[0]["url"].endswith(".pdf")


@pytest.mark.integration
def test_resolve_tencent_stock_id():
    stock_id = resolve_hkex_stock_id("0700.HK")
    assert stock_id == 7609

@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_hkex_documents_live():
    from knowledge.fetchers.hkex_fetcher import fetch_hkex_documents

    result = await fetch_hkex_documents("0700.HK", max_docs=1, annual_only=True)
    assert result.get("stock_id") == 7609
    assert result.get("ingested", 0) >= 1 or not result.get("errors")
