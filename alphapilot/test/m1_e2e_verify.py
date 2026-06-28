"""M1 里程碑 E2E 验证：真实 PDF ingest → 检索"""
from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.pdf_parser import parse_pdf, parse_and_chunk, _extract_tables_with_pages
from knowledge.document_chunker import normalize_section_name, _make_semantic_chunk_id
from knowledge.document_ingest import ingest_file
from rag.retriever import retriever

PDF_PATH = "/tmp/tencent_q1_2026.pdf"
SYMBOL = "0700.HK"

print("=" * 70)
print("M1 E2E 验证：腾讯 Q1 2026 财报")
print("=" * 70)

# Step 1: 解析文本
print("\n--- Step 1: parse_pdf ---")
text = parse_pdf(PDF_PATH)
if text:
    print(f"  文本长度: {len(text)} chars")
    # 显示前 500 字符，看看标题结构
    lines = text.split("\n")
    headings = [l for l in lines if l.startswith("#")][:20]
    print(f"  标题行 (前 20):")
    for h in headings:
        print(f"    {h[:100]}")
else:
    print("  ❌ 文本提取失败")
    sys.exit(1)

# Step 2: 提取表格
print("\n--- Step 2: extract_tables ---")
tables = _extract_tables_with_pages(PDF_PATH)
print(f"  表格数: {len(tables)}")
for t in tables:
    print(f"    page={t['page']}, rows={t['rows']}, preview={t['markdown'][:80]}...")

# Step 3: parse_and_chunk（新逻辑：表格注入对应 section）
print("\n--- Step 3: parse_and_chunk ---")
metadata = {
    "symbol": SYMBOL,
    "doc_id": "0700.HK_earnings_Q1_2026",
    "doc_type": "earnings_call",
    "source": "HKEX",
    "publish_date": "2026-05-13",
    "report_period": "2026-03-31",
    "language": "en",
}
chunks = parse_and_chunk(PDF_PATH, metadata, doc_type="earnings_call")
print(f"  总 chunk 数: {len(chunks)}")

# Step 4: 验证 chunk_id 和 section 元数据
print("\n--- Step 4: chunk 元数据验证 ---")
section_counts = {}
table_chunks = 0
for c in chunks:
    cid = c.get("chunk_id", "")
    section = c.get("section", "")
    page = c.get("page", "")
    has_table = c.get("contains_table", False)
    content_preview = c.get("content", "")[:100].replace("\n", " ")

    section_counts[section] = section_counts.get(section, 0) + 1
    if has_table:
        table_chunks += 1

    print(f"  [{cid}]")
    print(f"    section=\"{section}\"  page={page}  contains_table={has_table}")
    print(f"    preview: {content_preview}...")
    print()

print(f"  章节分布: {section_counts}")
print(f"  含表格 chunk 数: {table_chunks}")

# Step 5: 验证 section 命名规则
print("\n--- Step 5: section 命名规则验证 ---")
sections_with_meaningful_name = [s for s in section_counts if s and s not in ("", "General")]
print(f"  有语义命名的章节: {sections_with_meaningful_name}")
if sections_with_meaningful_name:
    print("  ✅ 章节有具体名称（非空/General）")
else:
    print("  ⚠️ 章节均为空或 General — markitdown 标题转换可能有问题")

# Step 6: 验证 chunk_id 格式
print("\n--- Step 6: chunk_id 格式验证 ---")
all_ids = [c.get("chunk_id", "") for c in chunks]
# 格式: {symbol}_{doc_type}_{section_slug}[_p{page}]_i{index}
# symbol 含 . 也是合法的（如 0700.HK）
import re
id_pattern = re.compile(r"^[\w.]+_[\w]+_[\w]+(_p\d+)?_i\d+$")
matching = [cid for cid in all_ids if id_pattern.match(cid)]
print(f"  符合新格式的 chunk_id: {len(matching)}/{len(all_ids)}")
print(f"  示例: {all_ids[:3]}")
if len(matching) == len(all_ids):
    print("  ✅ 所有 chunk_id 符合语义化格式")
else:
    print(f"  ⚠️ {len(all_ids) - len(matching)} 个 chunk_id 格式不符")
    bad = [cid for cid in all_ids if not id_pattern.match(cid)]
    print(f"  不符示例: {bad[:3]}")

# Step 7: ingest 入库
print("\n--- Step 7: ingest 入库 ---")
written = ingest_file(PDF_PATH, metadata, doc_type="earnings_call")
print(f"  写入 chunk 数: {written}")
if written > 0:
    print("  ✅ ingest 成功")
else:
    print("  ⚠️ ingest 返回 0（可能已存在或被跳过）")

print()
print("=" * 70)
print("E2E 验证完成")
print("=" * 70)
