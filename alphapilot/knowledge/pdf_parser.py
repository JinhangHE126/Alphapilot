"""
PDF 解析模块。
使用 markitdown 将 PDF 转为 Markdown，再提取表格、分块。
"""
from __future__ import annotations

import os
import tempfile
from typing import List, Dict, Any, Optional

from knowledge.document_chunker import chunk_document
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


def extract_tables(file_path: str) -> List[str]:
    """
    从 PDF 中提取表格，每表转为 Markdown 格式。
    使用 camelot-py（需要 Java 运行时）或 pdfplumber 作为回退。
    """
    tables: List[str] = []
    if not os.path.exists(file_path):
        return tables

    # 尝试 camelot
    try:
        import camelot
        camelot_tables = camelot.read_pdf(file_path, pages="all", flavor="lattice")
        for t in camelot_tables:
            md = t.df.to_markdown(index=False)
            tables.append(md)
        if tables:
            print(f"✅ camelot extracted {len(tables)} tables from {file_path}")
            return tables
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️ camelot failed: {e}")

    # 回退 pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table and len(table) > 0:
                        header = table[0]
                        rows = table[1:] if len(table) > 1 else []
                        md_rows = ["| " + " | ".join(str(c) for c in header) + " |"]
                        md_rows.append("|" + "|".join(["---"] * len(header)) + "|")
                        for row in rows:
                            md_rows.append("| " + " | ".join(str(c) for c in row) + " |")
                        tables.append("\n".join(md_rows))
        if tables:
            print(f"✅ pdfplumber extracted {len(tables)} tables from {file_path}")
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️ pdfplumber failed: {e}")

    return tables


def parse_and_chunk(
    file_path: str,
    metadata: Dict[str, str],
    doc_type: str = "annual_report",
) -> List[Dict[str, Any]]:
    """
    一站式：PDF 解析 → 表格提取 → 分块。
    返回 [{chunk_id, content, symbol, doc_type, ...}]。
    """
    text = parse_pdf(file_path)
    if not text:
        print(f"❌ Failed to extract text from {file_path}")
        return []

    # 附加文件名信息
    file_name = metadata.get("doc_id", os.path.basename(file_path))

    # 提取表格并追加到文本末尾
    tables = extract_tables(file_path)
    if tables:
        text += "\n\n## Extracted Tables\n\n"
        for i, table_md in enumerate(tables, 1):
            text += f"### Table {i}\n\n{table_md}\n\n"

    # 分块
    chunks = chunk_document(doc_type, text, metadata)
    print(f"📄 Parsed {file_name}: {len(tables)} tables, {len(chunks)} chunks")
    return chunks
