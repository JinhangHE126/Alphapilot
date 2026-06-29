"""3.1.5 测试：章节切分、chunk_id 格式、表格 section 挂载、HKEX ingest 回归。"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.document_chunker import (
    normalize_section_name,
    _sanitize_section_name,
    _section_to_slug,
    _make_semantic_chunk_id,
    chunk_by_headings,
    chunk_semantic,
    chunk_with_metadata,
    chunk_document,
)
from knowledge.pdf_parser import (
    _estimate_page_for_position,
    _inject_tables_into_sections,
)


# ═══════════════════════════════════════════════════════════
# 章节检测
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("raw,expected", [
    # 美股 10-K
    ("Item 1A. Risk Factors", "Risk Factors"),
    ("Item 7. Management's Discussion and Analysis", "MD&A"),
    ("Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
     "Quantitative and Qualitative Disclosures About Market Risk"),
    ("Item 8. Financial Statements and Supplementary Data", "Financial Statements"),
    ("Item 1. Business", "Business"),
    ("Item 2. Properties", "Properties"),
    ("Item 3. Legal Proceedings", "Legal Proceedings"),
    ("Item 5. Market for Registrant's Common Equity",
     "Market for Registrant's Common Equity"),
    ("Item 6. Selected Financial Data", "Selected Financial Data"),
    ("Item 9A. Controls and Procedures", "Controls and Procedures"),
    # 港股 / 中文
    ("风险因素", "Risk Factors"),
    ("風險因素", "Risk Factors"),
    ("管理层讨论与分析", "MD&A"),
    ("管理層討論與分析", "MD&A"),
    ("MD&A", "MD&A"),
    ("经营情况讨论与分析", "MD&A"),
    ("财务状况", "Financial Condition"),
    ("财务报表", "Financial Statements"),
    ("公司治理报告", "Corporate Governance"),
    ("企业管治报告", "Corporate Governance"),
    ("ESG报告", "ESG"),
    ("主营业务分析", "Business Overview"),
    ("行业概览", "Industry Overview"),
    ("风险管理", "Risk Management"),
    # 未匹配时保持原文
    ("Some Random Title", "Some Random Title"),
    ("", ""),
])
def test_normalize_section_name(raw, expected):
    assert normalize_section_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("", "General"),
    ("# #", "General"),
    ("##", "General"),
    ("CONDENSED CONSOLIDATED INCOME STATEMENT", "Financial Statements"),
    ("Some Random Title", "Some Random Title"),
])
def test_sanitize_section_name(raw, expected):
    assert _sanitize_section_name(raw) == expected


# ═══════════════════════════════════════════════════════════
# chunk_id 格式
# ═══════════════════════════════════════════════════════════

def test_section_to_slug():
    assert _section_to_slug("Risk Factors") == "Risk_Factors"
    assert _section_to_slug("MD&A") == "MDA"
    assert _section_to_slug("") == "General"
    assert _section_to_slug("管理层讨论与分析") == "管理层讨论与分析"


def test_semantic_chunk_id_format():
    """chunk_id 格式: {symbol}_{doc_type}_{section_slug}_p{page}[_i{index}]"""
    cid = _make_semantic_chunk_id("AAPL", "annual", "Risk Factors", "45", 1)
    assert cid == "AAPL_annual_Risk_Factors_p45_i01"

    cid2 = _make_semantic_chunk_id("0700.HK", "annual", "MD&A", "120", 2)
    assert cid2 == "0700.HK_annual_MDA_p120_i02"

    cid3 = _make_semantic_chunk_id("TSLA", "annual", "", "", 1)
    assert cid3 == "TSLA_annual_General_i01"

    # 无 symbol 用 doc_id 前缀
    cid4 = _make_semantic_chunk_id("", "earnings_call", "Risk Factors", "10", 3,
                                   doc_id="MSFT_earnings_2024Q3")
    # _ is \w, so earnings_call stays as-is
    assert "MSFT_earnings_call_Risk_Factors_p10_i03" in cid4 or \
           "MSFT_earningscall_Risk_Factors_p10_i03" in cid4


def test_semantic_chunk_id_unique():
    """同一 section 内多个 chunk 的 id 不重复。"""
    ids = set()
    for i in range(1, 6):
        cid = _make_semantic_chunk_id("AAPL", "annual", "Risk Factors", "45", i)
        assert cid not in ids, f"Duplicate chunk_id: {cid}"
        ids.add(cid)
    assert len(ids) == 5


# ═══════════════════════════════════════════════════════════
# 章节切分
# ═══════════════════════════════════════════════════════════

def test_chunk_by_headings_sections():
    text = (
        "# Item 1A. Risk Factors\n"
        "Our business faces significant risks.\n\n"
        "## Market Risk\n"
        "Changes in interest rates may affect earnings.\n\n"
        "# Item 7. MD&A\n"
        "Revenue grew 30% year over year."
    )
    sections = chunk_by_headings(text)
    assert len(sections) >= 3

    section_names = [s["section"] for s in sections]
    assert "Risk Factors" in section_names
    assert "MD&A" in section_names


def test_chunk_semantic():
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = chunk_semantic(text, chunk_size=500)
    assert len(chunks) >= 1
    assert "Paragraph one" in chunks[0]


# ═══════════════════════════════════════════════════════════
# chunk_with_metadata
# ═══════════════════════════════════════════════════════════

def test_chunk_with_metadata_annual_report():
    text = (
        "# Item 1A. Risk Factors\n"
        "Our business faces significant risks. " * 10 + "\n\n"
        "# Item 7. MD&A\n"
        "Revenue grew 30% year over year. " * 10
    )
    meta = {
        "symbol": "AAPL",
        "doc_id": "AAPL_annual_2024",
        "doc_type": "annual_report",
        "source": "SEC",
    }
    chunks = chunk_with_metadata("annual_report", text, meta)
    assert len(chunks) >= 2

    for c in chunks:
        assert "chunk_id" in c
        assert "content" in c
        assert "section" in c
        assert "symbol" in c
        # chunk_id 应包含 symbol
        assert "AAPL" in c["chunk_id"]
        # 不应是旧格式的纯数字 index
        assert not c["chunk_id"].endswith("0000")  # 旧格式


def test_chunk_document_convenience():
    text = "Simple news article about AAPL earnings."
    meta = {"symbol": "AAPL", "doc_type": "news", "source": "Reuters"}
    chunks = chunk_document("news", text, meta)
    assert len(chunks) == 1
    assert "AAPL" in chunks[0]["chunk_id"]


# ═══════════════════════════════════════════════════════════
# 表格 section 挂载
# ═══════════════════════════════════════════════════════════

def test_estimate_page_for_position():
    text = "A" * 1000  # 1000 chars
    assert _estimate_page_for_position(0, text, 10) == 1
    assert _estimate_page_for_position(500, text, 10) == 6
    assert _estimate_page_for_position(999, text, 10) == 10
    assert _estimate_page_for_position(0, text, 1) == 1


def test_inject_tables_into_sections():
    sections = [
        {"section": "Risk Factors", "level": 1, "content": "# Risk Factors\nRisk text."},
        {"section": "MD&A", "level": 1, "content": "# MD&A\nRevenue discussion."},
    ]
    tables = [
        {"page": 15, "markdown": "| ColA | ColB |\n| --- | --- |\n| 1 | 2 |", "rows": 1},
        {"page": 45, "markdown": "| X | Y |\n| --- | --- |\n| a | b |", "rows": 1},
    ]
    full_text = "# Risk Factors\nRisk text.\n# MD&A\nRevenue discussion."
    total_pages = 60

    result = _inject_tables_into_sections(sections, tables, full_text, total_pages)
    assert len(result) == 2

    # Risk Factors section 应包含第一个表格（page 15 在前半）
    rf = result[0]
    assert rf["contains_table"] is True
    assert "ColA" in rf["content"]

    # MD&A section 应包含第二个表格（page 45 在后半）
    mda = result[1]
    assert mda["contains_table"] is True
    assert "X" in mda["content"]


def test_inject_tables_no_tables():
    """无表格时 section 不应被修改。"""
    sections = [{"section": "Intro", "level": 1, "content": "Intro text."}]
    result = _inject_tables_into_sections(sections, [], "text", 10)
    assert result[0]["content"] == "Intro text."
    assert result[0].get("contains_table") is None


def test_inject_tables_section_field_not_Extracted_Tables():
    """表格挂载的 section 不应为 'Extracted Tables'。"""
    sections = [
        {"section": "Risk Factors", "level": 1, "content": "# Risk Factors\nContent."},
    ]
    tables = [{"page": 3, "markdown": "| A |\n| --- |\n| 1 |", "rows": 1}]
    text = "# Risk Factors\nContent."
    result = _inject_tables_into_sections(sections, tables, text, 5)
    # section 名应保持 "Risk Factors" 而非 "Extracted Tables"
    assert result[0]["section"] == "Risk Factors"


# ═══════════════════════════════════════════════════════════
# HKEX fetcher 回归（快速 smoke）
# ═══════════════════════════════════════════════════════════

def test_hkex_fetcher_import():
    """确保 HKEX fetcher 在新 chunker 下可正常导入。"""
    try:
        from knowledge.fetchers.hkex_fetcher import (
            _hkex_display_code,
            _parse_html_listings,
            _publish_date_from_url,
        )
        assert _hkex_display_code("0700.HK") == "00700"
        assert bool(_parse_html_listings)
        assert bool(_publish_date_from_url)
    except ModuleNotFoundError as e:
        if "yfinance" in str(e) or "sentence" in str(e):
            pytest.skip(f"Missing dependency: {e}")
        raise


def test_document_ingest_chain_import():
    """确保 document_ingest 链路可正常导入。"""
    from knowledge.document_ingest import (
        ingest_file,
        ingest_text,
        parse_file_to_chunks,
    )
    assert bool(ingest_file)
    assert bool(ingest_text)
    assert bool(parse_file_to_chunks)
