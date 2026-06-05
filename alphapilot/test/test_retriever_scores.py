import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mock heavy langchain deps so tests run without full FAISS/HuggingFace install.
# The test uses FakeVectorStore – no real vectorstore or embedding model needed.
_mock_langchain_community = MagicMock()
_mock_langchain_huggingface = MagicMock()
sys.modules["langchain_community"] = _mock_langchain_community
sys.modules["langchain_community.vectorstores"] = MagicMock()
sys.modules["langchain_huggingface"] = _mock_langchain_huggingface

from langchain_core.documents import Document  # noqa: E402
from rag.retriever import RagRetriever  # noqa: E402
from knowledge.ingest_service import upsert_packet  # noqa: E402
from schemas.evidence_packet import EvidencePacket, Coverage, Fact  # noqa: E402


class FakeVectorStore:
    def __init__(self):
        self._docs: list[Document] = []

    def add_documents(self, docs):
        self._docs.extend(docs)

    def similarity_search_with_score(self, query, k=5):
        docs = self._docs[:k]
        # Deterministic mock distances: first doc best, second doc weaker.
        distances = [0.0, 1.0, 2.0, 3.0, 4.0]
        out = []
        for idx, d in enumerate(docs):
            out.append((d, distances[min(idx, len(distances) - 1)]))
        return out

    def similarity_search(self, query, k=5):
        return self._docs[:k]

    def save_local(self, _path):
        return None


def _fresh_retriever() -> RagRetriever:
    r = RagRetriever.__new__(RagRetriever)
    r.vectorstore = FakeVectorStore()
    r.embedding_model = object()
    r._known_doc_ids = set()
    return r


def _make_packet(symbol: str = "TSLA") -> EvidencePacket:
    return EvidencePacket(
        symbol=symbol,
        request_type="comprehensive_analysis",
        coverage=Coverage(),
        evidence_score=80,
        facts=[
            Fact(
                field="current_price",
                value=123.45,
                unit="USD",
                period="latest",
                source="yfinance",
                as_of_date="2026-06-05",
                confidence=0.95,
                confidence_tier="machine",
            )
        ],
    )


def test_distance_to_similarity_monotonic():
    assert RagRetriever._distance_to_similarity(0.0) == 1.0
    assert RagRetriever._distance_to_similarity(1.0) > RagRetriever._distance_to_similarity(2.0)
    assert RagRetriever._distance_to_similarity(2.0) > RagRetriever._distance_to_similarity(5.0)


def test_upserted_record_can_be_retrieved(monkeypatch):
    fake_retriever = _fresh_retriever()

    from knowledge import ingest_service
    monkeypatch.setattr(ingest_service, "vectorstore", fake_retriever)

    packet = _make_packet("TSLA")
    ingest_result = upsert_packet(packet)
    assert ingest_result["ingested"] >= 1

    hits = fake_retriever.retrieve_with_scores("TSLA current price", k=5)
    assert len(hits) >= 1
    m = hits[0].metadata
    assert m.get("symbol") == "TSLA"
    assert m.get("as_of_date") == "2026-06-05"
    assert "expires_at" in m
    assert m.get("data_type") == "market_data"


def test_expired_record_is_filtered():
    fake_retriever = _fresh_retriever()
    expired_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    valid_doc = Document(
        page_content="current_price: 123.45",
        metadata={
            "symbol": "TSLA",
            "source": "yfinance",
            "as_of_date": "2026-06-05",
            "data_type": "market_data",
            "expires_at": expired_at,
        },
    )
    fake_retriever.vectorstore.add_documents([valid_doc])

    hits = fake_retriever.retrieve_with_scores("TSLA", k=5)
    assert hits == []
