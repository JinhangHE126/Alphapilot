from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.sensitive_scanner import REDACTED, scan


def test_scan_redacts_email_and_phone():
    text = "联系 support@example.com 或 13812345678 获取帮助"
    result = scan(text)
    assert result.redacted
    assert "email" in result.hits
    assert "phone" in result.hits
    assert REDACTED in result.text
    assert "support@example.com" not in result.text
    assert "13812345678" not in result.text


def test_scan_redacts_cn_id():
    text = "身份证号 110101199001011234 仅供测试"
    result = scan(text)
    assert result.redacted
    assert "cn_id" in result.hits
    assert "110101199001011234" not in result.text


def test_scan_clean_text_unchanged():
    text = "Tesla revenue grew 15% year over year in FY2024."
    result = scan(text)
    assert not result.redacted
    assert result.text == text


def test_ingest_chunks_redacts_before_vectorstore():
    from unittest.mock import patch

    from knowledge.document_ingest import ingest_chunks

    chunks = [
        {
            "chunk_id": "test_redact_chunk_1",
            "content": "联系人 support@example.com",
            "symbol": "TEST",
            "source": "user_uploaded",
            "doc_id": "test_doc",
            "doc_type": "research_report",
            "section": "",
            "page": "",
            "publish_date": "2025-01-01",
            "report_period": "",
            "contains_table": False,
            "language": "en",
        }
    ]
    with patch("knowledge.document_ingest.retriever.add_document_chunks") as mock_add:
        mock_add.return_value = 1
        written = ingest_chunks(
            chunks,
            user_session_id="user_42",
            is_user_upload=True,
            max_docs_per_symbol=None,
        )
    assert written == 1
    sent = mock_add.call_args[0][0][0]
    assert REDACTED in sent["content"]
    assert "support@example.com" not in sent["content"]
    assert sent["user_session_id"] == "user_42"
    assert sent["confidence_tier"] == "user_submitted"
    assert sent["source"] == "user_uploaded"
