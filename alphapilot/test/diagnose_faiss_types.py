"""通过 retriever API 直接诊断 FAISS _type 分布。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.retriever import retriever

print("=" * 60)
print("  FAISS 向量库 _type 诊断 (via retriever API)")
print("=" * 60)

vs = retriever.vectorstore
if not vs:
    print("  ❌ vectorstore is None")
    sys.exit(1)

# 通过 similarity_search_with_score 不加过滤，看全量
# 先用一个通用 query 检索
try:
    results = vs.similarity_search_with_score("financial report annual earnings", k=100)
    print(f"\n  similarity_search 返回: {len(results)} 条")

    from collections import Counter
    type_counts = Counter()
    symbol_counts = Counter()
    for doc, score in results:
        meta = doc.metadata or {}
        t = meta.get('_type', 'MISSING')
        s = meta.get('symbol', '?')
        type_counts[t] += 1
        symbol_counts[s] += 1

    if not type_counts:
        print("  ⚠️  metadata 全为空")
    else:
        print(f"\n  按 _type 分布:")
        for t, c in type_counts.most_common():
            print(f"    {t}: {c}")
        print(f"\n  按 symbol 分布:")
        for s, c in symbol_counts.most_common():
            print(f"    {s}: {c}")
except Exception as e:
    print(f"  similarity_search 失败: {e}")
    import traceback
    traceback.print_exc()

# 直接看 FAISS index 的 ntotal
try:
    ntotal = vs.index.ntotal
    print(f"\n  FAISS index.ntotal: {ntotal}")
except Exception as e:
    print(f"\n  index.ntotal 获取失败: {e}")

# 尝试 docstore 遍历
try:
    docstore = vs.docstore
    print(f"  docstore 类型: {type(docstore).__name__}")
    if hasattr(docstore, '_dict'):
        items = docstore._dict
        print(f"  docstore._dict 条目: {len(items)}")
        from collections import Counter
        tc = Counter()
        for k, v in list(items.items())[:100]:
            meta = getattr(v, 'metadata', {}) or {}
            tc[meta.get('_type', 'MISSING')] += 1
        print(f"  前100条 _type 分布: {dict(tc)}")
    elif isinstance(docstore, dict):
        print(f"  docstore 条目: {len(docstore)}")
except Exception as e:
    print(f"  docstore 遍历失败: {e}")

print("=" * 60)
