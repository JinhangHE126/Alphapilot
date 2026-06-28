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


# ═══════════════════════════════════════════════════════════
# 3.1.3 财报章节识别规则
# ═══════════════════════════════════════════════════════════

_SECTION_RULES: list[tuple[str, str]] = [
    # 美股 10-K / 10-Q
    (r"\bItem\s+1A[.\s]", "Risk Factors"),
    (r"\bItem\s+7[.\s]", "MD&A"),
    (r"\bItem\s+7A[.\s]", "Quantitative and Qualitative Disclosures About Market Risk"),
    (r"\bItem\s+8[.\s]", "Financial Statements"),
    (r"\bItem\s+1[.\s]", "Business"),
    (r"\bItem\s+2[.\s]", "Properties"),
    (r"\bItem\s+3[.\s]", "Legal Proceedings"),
    (r"\bItem\s+5[.\s]", "Market for Registrant's Common Equity"),
    (r"\bItem\s+6[.\s]", "Selected Financial Data"),
    (r"\bItem\s+9A[.\s]", "Controls and Procedures"),
    # 港股 / 中文年报
    (r"风险因素", "Risk Factors"),
    (r"風險因素", "Risk Factors"),
    (r"管理层讨论", "MD&A"),
    (r"管理層討論", "MD&A"),
    (r"管理层[的]?分析", "MD&A"),
    (r"经营(情况)?讨论(与|及|和)?分析", "MD&A"),
    (r"經營(情況)?討論(與|及|和)?分析", "MD&A"),
    (r"\bMD&A\b", "MD&A"),
    (r"財務[狀状]況", "Financial Condition"),
    (r"财务状况", "Financial Condition"),
    (r"财务报表", "Financial Statements"),
    (r"財務報表", "Financial Statements"),
    (r"公司治理", "Corporate Governance"),
    (r"企业管治", "Corporate Governance"),
    (r"企業管治", "Corporate Governance"),
    (r"\bESG\b", "ESG"),
    (r"ESG(报告|報告)?", "ESG"),
    (r"环境[、,社会及管治]", "ESG"),
    (r"主营业务", "Business Overview"),
    (r"主營業務", "Business Overview"),
    (r"行业[概览览]", "Industry Overview"),
    (r"行業[概覽览]", "Industry Overview"),
    (r"风险[管理]", "Risk Management"),
    (r"風險[管理]", "Risk Management"),
]


def normalize_section_name(raw_name: str) -> str:
    """
    根据预定义规则将原始标题映射为标准化章节名。
    美股 10-K Item 1A → "Risk Factors"、Item 7 → "MD&A"；
    港股关键词 → 对应英文标准名称。
    """
    if not raw_name or not raw_name.strip():
        return raw_name

    name = raw_name.strip()
    for pattern, canonical in _SECTION_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            return canonical
    return name


def _section_to_slug(sec_name: str) -> str:
    """章节名 → URL 安全标识（用于 chunk_id）。"""
    if not sec_name:
        return "General"
    # 清洗掉纯标点/空格/井号等无意义字符组成的名称
    cleaned = re.sub(r"[^\w]", "", sec_name)
    if not cleaned:
        return "General"
    # 去特殊字符，空格/连字符→下划线，取前 50 字符
    slug = re.sub(r"[^\w\s-]", "", sec_name)
    slug = re.sub(r"[\s-]+", "_", slug).strip("_")
    return slug[:50] if slug else "General"


# ═══════════════════════════════════════════════════════════
# 分块函数
# ═══════════════════════════════════════════════════════════

def chunk_by_headings(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[Dict[str, Any]]:
    """
    按 Markdown 标题层级切分章节。返回 [{section, level, content}]。
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
            raw_title = title_match.group(2).strip()
            title = normalize_section_name(raw_title)
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


# ═══════════════════════════════════════════════════════════
# 3.1.4 语义化 chunk_id
# ═══════════════════════════════════════════════════════════

_SAFE_SECTION_SLUG_CACHE: Dict[str, str] = {}


def _make_semantic_chunk_id(
    symbol: str,
    doc_type: str,
    section: str,
    page: str,
    index: int,
    doc_id: str = "",
) -> str:
    """
    生成语义化 chunk_id。
    格式：{symbol}_{doc_type}_{section_slug}_p{page}[_i{index}]

    示例：
      AAPL_annual_Risk_Factors_p45
      0700.HK_annual_MDA_p120_i02
    """
    if symbol:
        safe_symbol = re.sub(r"[^\w.]", "", symbol)
    elif doc_id:
        safe_symbol = re.sub(r"[^\w.]", "", doc_id.split("_")[0])
    else:
        safe_symbol = "UNK"

    safe_doctype = re.sub(r"[^\w]", "", doc_type or "doc")

    # section slug（带缓存）
    cache_key = section or ""
    if cache_key not in _SAFE_SECTION_SLUG_CACHE:
        _SAFE_SECTION_SLUG_CACHE[cache_key] = _section_to_slug(section)
    slug = _SAFE_SECTION_SLUG_CACHE[cache_key]

    page_part = f"_p{page}" if page else ""

    # index 用于同一 section 内多个 chunk 去重
    idx_part = f"_i{index:02d}"

    return f"{safe_symbol}_{safe_doctype}_{slug}{page_part}{idx_part}"


def _build_chunk_results(
    sections: List[Dict[str, Any]],
    metadata: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    将切好的 section 列表转为带完整元数据的 chunk 列表。
    供 pdf_parser.parse_and_chunk() 和 chunk_with_metadata() 共用。
    """
    doc_id = metadata.get("doc_id", "")
    symbol = metadata.get("symbol", "")
    doc_type = metadata.get("doc_type", "annual_report")

    results: List[Dict[str, Any]] = []
    section_counter: Dict[str, int] = {}

    for i, c in enumerate(sections):
        sec_name = c.get("section", "")
        page = c.get("page", "")
        contains_table = c.get("contains_table", False)

        # 同一 section 内的 chunk 计数（支持去重）
        count_key = f"{sec_name}_{page}"
        section_counter[count_key] = section_counter.get(count_key, 0) + 1
        seq = section_counter[count_key]

        chunk_id = _make_semantic_chunk_id(
            symbol=symbol,
            doc_type=doc_type,
            section=sec_name,
            page=page,
            index=seq,
            doc_id=doc_id,
        )

        chunk = {
            "chunk_id": chunk_id,
            "content": c["content"],
            "section": sec_name,
            **metadata,
        }
        if contains_table:
            chunk["contains_table"] = True
        if page:
            chunk["page"] = page
        results.append(chunk)

    return results


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
        sections = chunk_by_headings(text, chunk_size=1200, overlap=200)
    else:
        chunks_raw = chunk_semantic(text, chunk_size=800, overlap=150)
        sections = [{"section": "", "level": 0, "content": c} for c in chunks_raw]

    return _build_chunk_results(sections, metadata)


# ── 便捷函数 ──
def chunk_document(doc_type: str, text: str, metadata: Dict[str, str]) -> List[Dict[str, Any]]:
    """一站式分块入口。"""
    return chunk_with_metadata(doc_type, text, metadata)
