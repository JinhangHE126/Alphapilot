"""Automated document fetchers (Phase 3)."""
from knowledge.fetchers.hkex_fetcher import fetch_hkex_documents
from knowledge.fetchers.sec_fetcher import fetch_sec_filings
from knowledge.fetchers.news_fetcher import fetch_news_documents

__all__ = ["fetch_hkex_documents", "fetch_sec_filings", "fetch_news_documents"]
