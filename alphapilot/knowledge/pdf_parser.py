"""
PDF 解析模块。
使用 markitdown 将 PDF 转为 Markdown，再提取表格、分块。
"""
from __future__ import annotations

import os
import re
import tempfile
from typing import List, Dict, Any, Optional

from knowledge.document_chunker import chunk_document, _SECTION_RULES
from knowledge.pdf_env import check_pdf_parse_dependencies


def parse_pdf(file_path: str) -> Optional[str]:
    """
    将 PDF 文件转为 Markdown 文本。
    优先使用 markitdown，失败时回退到 pymupdf(fitz)。
    """
    if not os.path.exists(file_path):
        print(f"⚠️ PDF file not found: {file_path}")
        return None

    # 尝试 markitdown
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(file_path)
        text = result.text_content
        if text and len(text.strip()) > 100:
            print(f"✅ markitdown parsed PDF: {file_path} ({len(text)} chars)")
            return text
    except ImportError:
        print("⚠️ markitdown not installed, trying pymupdf fallback")
    except Exception as e:
        print(f"⚠️ markitdown failed: {e}, trying pymupdf fallback")

    # 回退 pymupdf
    try:
        import fitz
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        text = "\n\n".join(pages)
        if text.strip():
            # 纯文本无 markdown 标题 → 推断章节结构
            text = _infer_markdown_headings(text)
            print(f"✅ pymupdf parsed PDF: {file_path} ({len(text)} chars)")
            return text
    except ImportError:
        print("⚠️ pymupdf(fitz) not installed")
    except Exception as e:
        print(f"⚠️ pymupdf failed: {e}")

    caps = check_pdf_parse_dependencies()
    if not caps["text_extraction_ready"]:
        print(
            "❌ PDF text extraction unavailable. "
            "Install: pip install markitdown pymupdf"
        )
    return None


def _infer_markdown_headings(text: str) -> str:
    """
    对非 Markdown 纯文本（如 pymupdf 输出）推断章节结构。
    识别常见财报段落标题（ALL-CAPS、中文粗体标题等），添加 ## 前缀。
    """
    lines = text.split("\n")
    result: list[str] = []
    # 已知的财报章节关键词（按匹配后不应被 ## 覆盖的原生标题跳过）
    has_existing_headings = any(
        line.strip().startswith("#") for line in lines if line.strip()
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue

        # 跳过已有 markdown 标题
        if stripped.startswith("#"):
            result.append(line)
            continue

        # 全大写单行（可能是章节标题），且长度合理
        if (stripped.isupper() and len(stripped) > 3 and len(stripped) < 80
                and not stripped[0].isdigit()):
            result.append(f"## {stripped}")
            continue

        # 匹配常见中文财报章节
        for pattern, canonical in _SECTION_RULES:
            if (pattern.startswith(r"\bItem") or pattern == r"\bMD&A\b"
                    or pattern == r"\bESG\b"):
                continue  # 英文 Item 规则跳过（仅对中文文本处理）
            if re.search(pattern, stripped, re.IGNORECASE):
                result.append(f"## {stripped}")
                break
        else:
            result.append(line)

    return "\n".join(result)


def extract_tables(file_path: str) -> List[str]:
    """提取表格 Markdown（兼容旧接口，不含页码）。"""
    return [t["markdown"] for t in _extract_tables_with_pages(file_path)]


def _extract_tables_with_pages(file_path: str) -> List[Dict[str, Any]]:
    """
    从 PDF 中提取表格，优先 pdfplumber（轻量、免 Java），camelot 作为回退。
    返回 [{page, markdown, rows}]，page 为 1-based 页码。
    """
    result: List[Dict[str, Any]] = []
    if not os.path.exists(file_path):
        return result

    # ── 优先 pdfplumber（轻量，pip install pdfplumber 即可） ──
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table and len(table) > 0:
                        header = table[0]
                        rows = table[1:] if len(table) > 1 else []
                        if not header or all(c is None for c in header):
                            continue
                        md_rows = ["| " + " | ".join(str(c or "") for c in header) + " |"]
                        md_rows.append("|" + "|".join(["---"] * len(header)) + "|")
                        for row in rows:
                            md_rows.append("| " + " | ".join(str(c or "") for c in row) + " |")
                        result.append({
                            "page": page_num,
                            "markdown": "\n".join(md_rows),
                            "rows": len(rows),
                        })
        if result:
            print(f"✅ pdfplumber extracted {len(result)} tables from {file_path}")
            return result
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️ pdfplumber failed: {e}")

    # ── 回退 camelot（需要 Java 运行时） ──
    try:
        import camelot
        camelot_tables = camelot.read_pdf(file_path, pages="all", flavor="lattice")
        for t in camelot_tables:
            page_num = t.page if hasattr(t, 'page') else 1
            md = t.df.to_markdown(index=False)
            result.append({
                "page": int(page_num) if page_num else 1,
                "markdown": md,
                "rows": len(t.df),
            })
        if result:
            print(f"✅ camelot extracted {len(result)} tables from {file_path}")
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️ camelot failed: {e}")

    return result


def _estimate_page_for_position(
    position: int,
    text: str,
    total_pages: int,
) -> int:
    """根据字符位置估算所在页码（1-based）。"""
    if total_pages <= 1:
        return 1
    ratio = position / max(len(text), 1)
    return max(1, min(total_pages, int(ratio * total_pages) + 1))


def _inject_tables_into_sections(
    sections: List[Dict[str, Any]],
    tables_with_pages: List[Dict[str, Any]],
    text: str,
    total_pages: int,
) -> List[Dict[str, Any]]:
    """
    将表格 Markdown 注入到对应的章节 chunk 中。
    表格按页码匹配所属章节，不再堆在文末。
    """
    if not tables_with_pages:
        return sections

    # 计算每个 section 在原文中的起始位置（用于估算页码范围）
    pos = 0
    section_starts: List[int] = []
    for s in sections:
        content = s["content"]
        idx = text.find(content, pos)
        if idx >= 0:
            section_starts.append(idx)
            pos = idx + len(content)
        else:
            section_starts.append(pos)

    # 为每个 section 估算页码范围
    for s_idx, s in enumerate(sections):
        start_pos = section_starts[s_idx]
        start_page = _estimate_page_for_position(start_pos, text, total_pages)

        end_pos = section_starts[s_idx + 1] if s_idx + 1 < len(section_starts) else len(text)
        end_page = _estimate_page_for_position(end_pos, text, total_pages)

        # 找到属于此 section 页码范围内的表格
        section_tables = [
            t for t in tables_with_pages
            if start_page <= t["page"] <= end_page
        ]
        if section_tables:
            table_md = "\n\n---\n\n".join(t["markdown"] for t in section_tables)
            s["content"] = s["content"].rstrip() + f"\n\n### Tables (pages {start_page}-{end_page})\n\n{table_md}"
            s["contains_table"] = True
            s["page"] = str(start_page)

    return sections


def parse_and_chunk(
    file_path: str,
    metadata: Dict[str, str],
    doc_type: str = "annual_report",
) -> List[Dict[str, Any]]:
    """
    一站式：PDF 解析 → 表格提取 → 章节注入 → 分块。
    表格按页码归属对应章节，不再堆在文末。
    返回 [{chunk_id, content, symbol, doc_type, ...}]。
    """
    text = parse_pdf(file_path)
    if not text:
        print(f"❌ Failed to extract text from {file_path}")
        return []

    file_name = metadata.get("doc_id", os.path.basename(file_path))

    # 获取总页数（用于页码估算）
    total_pages = 1
    try:
        import fitz
        doc = fitz.open(file_path)
        total_pages = max(doc.page_count, 1)
        doc.close()
    except Exception:
        pass

    # 提取表格（带页码）
    tables_with_pages = _extract_tables_with_pages(file_path)

    # 先按标题切分章节
    from knowledge.document_chunker import chunk_by_headings, chunk_semantic
    if doc_type in ("annual_report", "earnings_call"):
        sections = chunk_by_headings(text, chunk_size=1200, overlap=200)
    else:
        sections_raw = chunk_semantic(text, chunk_size=800, overlap=150)
        sections = [{"section": "", "level": 0, "content": c} for c in sections_raw]

    # 将表格注入到对应章节
    if tables_with_pages:
        sections = _inject_tables_into_sections(sections, tables_with_pages, text, total_pages)

    # 分块（使用 chunk_with_metadata 的逻辑）
    from knowledge.document_chunker import _build_chunk_results

    chunks = _build_chunk_results(sections, metadata)
    print(f"📄 Parsed {file_name}: {len(tables_with_pages)} tables, {len(chunks)} chunks")
    return chunks
