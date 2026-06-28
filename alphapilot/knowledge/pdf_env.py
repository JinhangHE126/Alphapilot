"""
PDF / 文档解析依赖检查。
上传与 ingest 前可调用，避免静默失败。
"""
from __future__ import annotations

import importlib.util
from typing import Any


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_pdf_parse_dependencies() -> dict[str, Any]:
    """
    返回当前环境的 PDF 解析能力。
    - text_extraction_ready: markitdown 或 pymupdf 至少一个可用（上传 PDF 必需）
    - table_extraction: camelot 或 pdfplumber 可用（可选，增强表格提取）
    """
    markitdown = _has_module("markitdown")
    pymupdf = _has_module("fitz")
    camelot = _has_module("camelot")
    pdfplumber = _has_module("pdfplumber")
    return {
        "markitdown": markitdown,
        "pymupdf": pymupdf,
        "camelot": camelot,
        "pdfplumber": pdfplumber,
        "text_extraction_ready": markitdown or pymupdf,
        "table_extraction_ready": camelot or pdfplumber,
    }


def format_pdf_capability_message(caps: dict[str, Any] | None = None) -> str:
    caps = caps or check_pdf_parse_dependencies()
    lines = [
        "PDF parse capabilities:",
        f"  text (required): markitdown={caps['markitdown']}, pymupdf={caps['pymupdf']}",
        f"  tables (recommended): pdfplumber={caps['pdfplumber']} | camelot={caps['camelot']}",
    ]
    if not caps["text_extraction_ready"]:
        lines.append(
            "  ⚠️ No PDF text backend — run: pip install markitdown pymupdf"
        )
    if not caps["table_extraction_ready"]:
        lines.append(
            "  ℹ️ No table backend — optional: pip install pdfplumber"
        )
    elif not caps["pdfplumber"] and caps["camelot"]:
        lines.append(
            "  ℹ️ Using camelot (needs Java). For lighter setup: pip install pdfplumber"
        )
    return "\n".join(lines)


def log_pdf_capabilities() -> dict[str, Any]:
    caps = check_pdf_parse_dependencies()
    print(format_pdf_capability_message(caps))
    return caps


def require_text_extraction() -> None:
    """PDF 上传前调用；不可用则抛出 RuntimeError（由 API 转为 HTTP 503）。"""
    caps = check_pdf_parse_dependencies()
    if caps["text_extraction_ready"]:
        return
    raise RuntimeError(
        "PDF text extraction unavailable. Install at least one of: "
        "markitdown, pymupdf (pip install markitdown pymupdf). "
        "See requirements.txt and requirements-optional.txt."
    )
