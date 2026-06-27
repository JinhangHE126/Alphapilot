"""验证 RAG 文档上传是否成功 — 全链路诊断。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.retriever import retriever

print("=" * 60)
print("  RAG 文档上传诊断")
print("=" * 60)

# ═══ 1. FAISS 状态 ═══
print("\n[1] FAISS 向量库状态")
if retriever.vectorstore:
    print(f"    ✅ FAISS 已加载\n    📚 已知 doc_id 数量: {len(retriever._known_doc_ids)}")

    # 统计所有 _type=document_chunk 的 chunk
    try:
        # 不带 symbol 过滤，看全量
        all_results = retriever.retrieve_doc_chunks("annual report earnings", symbol="", k=100)
        by_symbol = {}
        by_type = {}
        for dc in all_results:
            sym = dc.get("symbol", "unknown")
            dt = dc.get("doc_type", "unknown")
            by_symbol.setdefault(sym, 0)
            by_symbol[sym] += 1
            by_type.setdefault(dt, 0)
            by_type[dt] += 1

        print(f"    总 document_chunk 数: {len(all_results)}")
        print(f"    按 symbol 分布: {dict(by_symbol)}")
        print(f"    按 doc_type 分布: {dict(by_type)}")
    except Exception as e:
        print(f"    ❌ 检索失败: {e}")
else:
    print("    ❌ FAISS 未初始化")
    sys.exit(1)

# ═══ 2. TSLA 文档内容抽样 ═══
print("\n[2] TSLA 文档 chunk 抽样")
tsla_results = retriever.retrieve_doc_chunks("TSLA financial analysis", symbol="TSLA", k=10)
print(f"    TSLA chunk 总数: {len(tsla_results)}")
for i, dc in enumerate(tsla_results[:5]):
    print(f"    [{i+1}] {dc['doc_id']} | type={dc['doc_type']} | source={dc['source']}")
    print(f"         section: {dc.get('section', 'N/A')}  period: {dc.get('report_period', 'N/A')}")
    print(f"         content: {dc['content'][:150]}...")

# ═══ 3. 问题判定 ═══
print("\n[3] 诊断结论")
tsla_all = retriever.retrieve_doc_chunks("TSLA", symbol="TSLA", k=50)
annual_types = [dc for dc in tsla_all if dc.get("doc_type") in ("annual_report", "earnings_call", "research_report")]
news_types = [dc for dc in tsla_all if dc.get("doc_type") == "news"]

if not tsla_all:
    print("    ❌ TSLA 没有任何 document chunk → 上传未成功或写入失败")
elif not annual_types and news_types:
    print("    ⚠️  TSLA 只有 news 类型 chunk（来自 yfinance 自动同步），没有用户上传的年报/电话会议")
    print("        → 请确认通过 /api/upload 或 CLI 上传了 PDF 且 ingest 成功")
elif annual_types:
    print(f"    ✅ TSLA 有 {len(annual_types)} 个年报/电话会议/研报 chunk")
    print(f"       有 {len(news_types)} 个 news chunk")
else:
    print(f"    ⚠️  TSLA 有 {len(tsla_all)} 个 chunk，类型未知")

print("=" * 60)
