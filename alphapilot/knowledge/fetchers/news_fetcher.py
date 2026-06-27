"""新闻标题 + 正文自动抓取与入库。"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

import aiohttp

from knowledge.document_ingest import ingest_text
from tools.news_tools import _extract_news_item, _fetch_news_list

_STRIP_TAGS = re.compile(r"<[^>]+>")


async def _fetch_article_body(session: aiohttp.ClientSession, url: str) -> str:
    if not url:
        return ""
    try:
        async with session.get(url, timeout=20, headers={"User-Agent": "AlphaPilot/1.0"}) as resp:
            if resp.status != 200:
                return ""
            html = await resp.text(errors="ignore")
            text = _STRIP_TAGS.sub(" ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:12000]
    except Exception:
        return ""


async def fetch_news_documents(
    symbol: str,
    *,
    max_articles: int = 5,
    fetch_body: bool = True,
) -> dict[str, Any]:
    """扩展 yfinance 新闻列表，将标题 + 摘要/正文写入文档向量库。"""
    try:
        news_list = _fetch_news_list(symbol)
    except Exception as exc:
        return {"symbol": symbol, "ingested": 0, "errors": [str(exc)]}

    ingested = 0
    skipped = 0
    errors: list[str] = []

    async with aiohttp.ClientSession(trust_env=True) as session:
        for raw in news_list[:max_articles]:
            item = _extract_news_item(raw)
            title = item.get("title", "")
            summary = item.get("summary", "")
            link = item.get("link", "")
            publisher = item.get("publisher", "Yahoo")

            body = summary
            if fetch_body and link:
                fetched = await _fetch_article_body(session, link)
                if fetched and len(fetched) > len(summary):
                    body = fetched

            if not title and not body:
                skipped += 1
                continue

            text = f"# {title}\n\nPublisher: {publisher}\n\n{body}\n\nSource: {link}"
            file_id = uuid.uuid4().hex[:8]
            doc_id = f"{symbol.upper()}_news_{file_id}"
            metadata = {
                "doc_id": doc_id,
                "symbol": symbol.upper(),
                "source": publisher or "Yahoo",
                "doc_type": "news",
                "publish_date": datetime.utcnow().date().isoformat(),
                "report_period": "",
                "language": "en",
            }
            try:
                written = ingest_text(text, metadata, doc_type="news")
                if written:
                    ingested += 1
                else:
                    skipped += 1
            except Exception as exc:
                skipped += 1
                errors.append(f"{title[:40]}: {exc}")

    return {"symbol": symbol, "ingested": ingested, "skipped": skipped, "errors": errors}
