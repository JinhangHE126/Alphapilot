#!/usr/bin/env python3
"""
CLI 文档入库工具。
用法:
  python cli_ingest_doc.py --symbol 0700.HK --type annual_report --source HKEX path/to/report.pdf
  python cli_ingest_doc.py --symbol TSLA --type research_report --source user_uploaded path/to/report.pdf
"""
import argparse
import sys
from pathlib import Path

# 项目根路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.pdf_parser import parse_and_chunk
from rag.retriever import retriever


def main():
    parser = argparse.ArgumentParser(description="文档入库：PDF → 分块 → FAISS")
    parser.add_argument("file", help="PDF 文件路径")
    parser.add_argument("--symbol", required=True, help="股票代码，如 0700.HK")
    parser.add_argument("--type", dest="doc_type", default="annual_report",
                        choices=["annual_report", "earnings_call", "research_report", "news"])
    parser.add_argument("--source", default="user_uploaded", help="来源: HKEX/SEC/user_uploaded")
    parser.add_argument("--publish-date", default="", help="发布日期 (YYYY-MM-DD)")
    parser.add_argument("--report-period", default="", help="报告期 (YYYY-MM-DD)")
    parser.add_argument("--language", default="zh", help="文档语言")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        sys.exit(1)

    metadata = {
        "doc_id": f"{args.symbol}_{args.doc_type}_{file_path.stem}",
        "symbol": args.symbol.upper(),
        "source": args.source,
        "doc_type": args.doc_type,
        "publish_date": args.publish_date or "",
        "report_period": args.report_period or "",
        "language": args.language,
        "page": "",
    }

    _ = retriever.vectorstore  # trigger init

    chunks = parse_and_chunk(str(file_path), metadata, doc_type=args.doc_type)
    if not chunks:
        print("❌ 未能从文档提取文本")
        sys.exit(1)

    written = retriever.add_document_chunks(chunks)
    print(f"✅ 成功入库 {written} 个 chunk (共 {len(chunks)} 个)")
    print(f"   symbol={args.symbol.upper()}  doc_type={args.doc_type}  source={args.source}")


if __name__ == "__main__":
    main()
