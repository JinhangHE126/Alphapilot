"""Phase 3 — 自动化文档摄取定时调度。"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from knowledge.fetchers import fetch_hkex_documents, fetch_news_documents, fetch_sec_filings
from rag.doc_registry import MAX_DOCS_PER_SYMBOL, prune_symbol_documents

_scheduler = None


def _watch_symbols() -> list[str]:
    raw = os.getenv("DOC_FETCH_SYMBOLS", "TSLA,AAPL,0700.HK")
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


async def fetch_documents_for_symbol(symbol: str) -> dict[str, Any]:
    """按标的类型调用对应 fetcher，并执行文档保留策略。"""
    symbol = symbol.upper()
    results: dict[str, Any] = {"symbol": symbol}

    if symbol.endswith(".HK"):
        results["hkex"] = await fetch_hkex_documents(symbol, max_docs=2)
    else:
        results["sec"] = await fetch_sec_filings(symbol, max_docs=2)

    results["news"] = await fetch_news_documents(symbol, max_articles=3)
    results["pruned"] = prune_symbol_documents(symbol, max_docs=MAX_DOCS_PER_SYMBOL)
    return results


async def run_fetch_cycle() -> list[dict[str, Any]]:
    symbols = _watch_symbols()
    if not symbols:
        return []
    print(f"📥 Document fetch cycle started for {len(symbols)} symbol(s)")
    outcomes: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            outcome = await fetch_documents_for_symbol(symbol)
            outcomes.append(outcome)
            print(f"✅ Fetch done: {symbol} → {outcome}")
        except Exception as exc:
            print(f"⚠️ Fetch failed for {symbol}: {exc}")
            outcomes.append({"symbol": symbol, "error": str(exc)})
    return outcomes


def start_document_scheduler():
    """
    启动 APScheduler 定时任务。
    需设置环境变量 DOC_FETCH_ENABLED=true 才会启用。
    """
    global _scheduler
    if os.getenv("DOC_FETCH_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        print("ℹ️ Document auto-fetch scheduler disabled (set DOC_FETCH_ENABLED=true)")
        return None

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        print("⚠️ apscheduler not installed; document scheduler disabled")
        return None

    if _scheduler is not None:
        return _scheduler

    interval_hours = int(os.getenv("DOC_FETCH_INTERVAL_HOURS", "6"))
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_fetch_cycle,
        trigger="interval",
        hours=interval_hours,
        id="doc_fetch_cycle",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    print(f"✅ Document fetch scheduler started (every {interval_hours}h)")
    return _scheduler


def stop_document_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


async def run_fetch_once() -> list[dict[str, Any]]:
    """手动触发一次全量抓取（CLI / 测试用）。"""
    return await run_fetch_cycle()
