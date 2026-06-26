"""
文档感知分块模块（Layout-aware + Structure-aware Chunking）。
支持按 Markdown 标题层级、段落语义、文档类型自适应分割。
"""
from __future__ import annotations

import re
from typing import List, Dict, Any


def _count_tokens_approx(text: str) -> int:
    """粗略 token 计数（中文按字符，英文按 4 字符 ≈ 1 token）。"""
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other_chars = len(text) - chinese_chars
    return chinese_chars + other_chars // 4


def chunk_by_headings(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[Dict[str, Any]]:
    """
    按 Markdown 标题层级切分章节。返回 [{section, content}]。
    处理逻辑：
    1. 按标题切分
    2. 每节的内容如果超过 chunk_size，内部按段落再细分
    3. 相邻 chunk 之间有 overlap 字符的上下文
    """
    if not text.strip():
        return []

    sections = re.split(r"\n(?=#{1,6}\s)", text)
    results: List[Dict[str, Any]] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # 提取标题行
        title_match = re.match(r"(#{1,6})\s+(.+)", section)
        if title_match:
            level = len(title_match.group(1))
            title = title_match.group(2).strip()
            body = section[title_match.end():].strip()
        else:
            level = 0
            title = ""
            body = section

        if _count_tokens_approx(body) <= chunk_size:
            results.append({
                "section": title,
                "level": level,
                "content": section.strip(),
            })
        else:
            # 大段内容按段落再细分
            paragraphs = re.split(r"\n\s*\n", body)
            current_chunk = title_match.group(0) + "\n\n" if title_match else ""
            current_tokens = _count_tokens_approx(current_chunk)

            for para in paragraphs:
                para_tokens = _count_tokens_approx(para)
                if current_tokens + para_tokens > chunk_size and current_chunk.strip():
                    results.append({
                        "section": title,
                        "level": level,
                        "content": current_chunk.strip(),
                    })
                    # overlap: 保留上一段末尾作为上下文
                    overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                    current_chunk = (
                        f"{title_match.group(0)}\n\n*(续 {title})*\n\n{overlap_text}\n\n{para}"
                        if title_match
                        else f"{overlap_text}\n\n{para}"
                    )
                    current_tokens = _count_tokens_approx(current_chunk)
                else:
                    current_chunk += "\n\n" + para if current_chunk else para
                    current_tokens += para_tokens

            if current_chunk.strip():
                results.append({
                    "section": title,
                    "level": level,
                    "content": current_chunk.strip(),
                })

    return results


def chunk_semantic(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    """
    基于段落 + token 计数的语义切分。
    优先保留段落完整性，不拆断句子；超过 chunk_size 时才按句子断点切割。
    """
    if not text.strip():
        return []

    paragraphs = re.split(r"\n\s*\n", text)
    chunks: List[str] = []
    current = ""
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _count_tokens_approx(para)
        if current_tokens + para_tokens > chunk_size and current:
            chunks.append(current.strip())
            # overlap: 保留末尾 overlap 字符
            overlap_text = current[-overlap:] if len(current) > overlap else current
            current = overlap_text + "\n\n" + para
            current_tokens = _count_tokens_approx(current)
        else:
            current = current + "\n\n" + para if current else para
            current_tokens += para_tokens

    if current.strip():
        chunks.append(current.strip())

    return chunks


def chunk_with_metadata(
    doc_type: str,
    text: str,
    metadata: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    根据文档类型选择分块策略，附加完整元数据。
    返回 [{chunk_id, content, ...metadata}]。
    """
    if not text.strip():
        return []

    # 选择分块策略
    if doc_type in ("annual_report", "earnings_call"):
        chunks = chunk_by_headings(text, chunk_size=1200, overlap=200)
    else:
        chunks_raw = chunk_semantic(text, chunk_size=800, overlap=150)
        chunks = [{"section": "", "level": 0, "content": c} for c in chunks_raw]

    # 附加元数据 + 生成 chunk_id
    results: List[Dict[str, Any]] = []
    doc_id = metadata.get("doc_id", "")
    symbol = metadata.get("symbol", "")

    for i, c in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk{i:04d}" if doc_id else f"{symbol}_chunk{i:04d}"
        results.append({
            "chunk_id": chunk_id,
            "content": c["content"],
            "section": c["section"],
            **metadata,
        })

    return results


# ── 便捷函数 ──
def chunk_document(doc_type: str, text: str, metadata: Dict[str, str]) -> List[Dict[str, Any]]:
    """一站式分块入口。"""
    return chunk_with_metadata(doc_type, text, metadata)
