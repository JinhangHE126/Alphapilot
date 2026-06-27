#!/usr/bin/env python3
"""
Phase 4 一键验收：建测试文件 → 上传 → Session 隔离检索 → 敏感信息打码检查。

用法（在 alphapilot 目录下）:

  # 推荐：经 HTTP 上传（需后端已启动 + 登录凭据）
  python scripts/verify_p4.py --username your_user --password your_pass

  # 或提供 token（跳过登录）
  VERIFY_P4_TOKEN=eyJ... python scripts/verify_p4.py

  # 无后端时：直连 ingest（跳过 Upload API，仍验 ingest + 检索 + 打码）
  python scripts/verify_p4.py --local --user-id 1

环境变量（可选）:
  VERIFY_P4_API_URL      默认 http://127.0.0.1:8000
  VERIFY_P4_USERNAME / VERIFY_P4_PASSWORD
  VERIFY_P4_TOKEN
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

SENSITIVE_EMAIL = "p4verify@example.com"
SENSITIVE_PHONE = "13812345678"


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def _step(title: str) -> None:
    print(f"\n▶ {title}")


def _http_json(
    method: str,
    url: str,
    *,
    data: dict | None = None,
    token: str = "",
    timeout: float = 60,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    body: bytes | None = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=body, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _multipart_upload(
    url: str,
    token: str,
    file_path: Path,
    fields: dict[str, str],
    timeout: float = 120,
) -> dict[str, Any]:
    boundary = f"----AlphapilotP4{uuid.uuid4().hex}"
    body = bytearray()

    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())

    content = file_path.read_bytes()
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
    )
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
    body.extend(content)
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    req = Request(url, data=bytes(body), headers=headers, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def login(base_url: str, username: str, password: str) -> tuple[str, str]:
    payload = _http_json(
        "POST",
        f"{base_url.rstrip('/')}/auth/login",
        data={"username": username, "password": password},
    )
    data = payload.get("data") or {}
    token = data.get("access_token", "")
    user_id = str(data.get("user_id", ""))
    if not token:
        raise RuntimeError(f"登录失败: {payload}")
    return token, user_id


def fetch_me(base_url: str, token: str) -> str:
    payload = _http_json("GET", f"{base_url.rstrip('/')}/auth/me", token=token)
    data = payload.get("data") or payload
    user_id = str(data.get("id", data.get("user_id", "")))
    if not user_id:
        raise RuntimeError(f"无法获取 user id: {payload}")
    return user_id


def create_test_file(tmp_dir: Path, marker: str) -> Path:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / f"p4_verify_{uuid.uuid4().hex[:8]}.txt"
    path.write_text(
        "\n".join(
            [
                marker,
                "",
                "AlphaPilot Phase 4 verification — private user research note.",
                "Tesla mid-term view: focus on margin and capacity utilization.",
                f"Contact: {SENSITIVE_EMAIL}, phone {SENSITIVE_PHONE}.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def upload_via_api(
    base_url: str,
    token: str,
    file_path: Path,
    symbol: str,
) -> dict[str, Any]:
    payload = _multipart_upload(
        f"{base_url.rstrip('/')}/upload/document",
        token,
        file_path,
        {
            "symbol": symbol,
            "doc_type": "research_report",
            "source": "user_uploaded",
            "language": "en",
        },
    )
    if payload.get("status") != "ok":
        raise RuntimeError(f"上传失败: {payload}")
    data = payload.get("data") or {}
    if not data.get("chunks"):
        raise RuntimeError(f"上传返回 0 chunks: {payload}")
    return data


def upload_via_local_ingest(
    file_path: Path,
    symbol: str,
    user_session_id: str,
) -> dict[str, Any]:
    from datetime import UTC, datetime

    from knowledge.document_ingest import ingest_file

    file_id = uuid.uuid4().hex[:12]
    doc_id = f"{symbol}_research_report_{file_id}"
    metadata = {
        "doc_id": doc_id,
        "symbol": symbol.upper(),
        "source": "user_uploaded",
        "doc_type": "research_report",
        "publish_date": datetime.now(UTC).isoformat(),
        "report_period": "",
        "language": "en",
        "page": "",
    }
    written = ingest_file(
        str(file_path),
        metadata,
        doc_type="research_report",
        user_session_id=user_session_id,
    )
    if not written:
        raise RuntimeError("ingest_file 写入 0 chunks")
    return {"doc_id": doc_id, "chunks": written, "symbol": symbol.upper()}


def find_marker_chunk(marker: str) -> dict[str, Any] | None:
    from rag.retriever import retriever

    if not retriever.vectorstore:
        raise RuntimeError("FAISS 未初始化，请确认 embedding 模型可用")

    for doc in retriever.vectorstore.docstore._dict.values():
        meta = doc.metadata or {}
        if meta.get("_type") != "document_chunk":
            continue
        if marker in (doc.page_content or ""):
            return {
                "content": doc.page_content,
                "metadata": meta,
            }
    return None


def check_redaction_and_metadata(chunk: dict[str, Any], owner_session_id: str) -> list[str]:
    errors: list[str] = []
    meta = chunk["metadata"]
    content = chunk["content"]

    if meta.get("source") != "user_uploaded":
        errors.append(f"source 应为 user_uploaded，实际 {meta.get('source')!r}")
    if meta.get("confidence_tier") != "user_submitted":
        errors.append(f"confidence_tier 应为 user_submitted，实际 {meta.get('confidence_tier')!r}")
    if str(meta.get("user_session_id", "")) != str(owner_session_id):
        errors.append(
            f"user_session_id 应为 {owner_session_id!r}，实际 {meta.get('user_session_id')!r}"
        )
    if SENSITIVE_EMAIL in content or SENSITIVE_PHONE in content:
        errors.append("向量库中仍含明文敏感信息（邮箱/电话）")
    if "[REDACTED]" not in content:
        errors.append("向量库 chunk 未包含 [REDACTED] 打码标记")
    return errors


def check_session_isolation(marker: str, symbol: str, owner_session_id: str) -> list[str]:
    from rag.retriever import retriever

    errors: list[str] = []

    public_hits = retriever.hybrid_retrieve(
        query=marker, symbol=symbol, k=10, user_session_id=""
    )
    if any(marker in h.get("content", "") for h in public_hits):
        errors.append("无 session 检索泄漏了私有 marker")

    owner_hits = retriever.hybrid_retrieve(
        query=marker, symbol=symbol, k=10, user_session_id=owner_session_id
    )
    if not any(marker in h.get("content", "") for h in owner_hits):
        errors.append(f"本人 session ({owner_session_id}) 未检索到私有 marker")

    wrong_id = f"wrong_{owner_session_id}_{uuid.uuid4().hex[:6]}"
    other_hits = retriever.hybrid_retrieve(
        query=marker, symbol=symbol, k=10, user_session_id=wrong_id
    )
    if any(marker in h.get("content", "") for h in other_hits):
        errors.append(f"错误 session ({wrong_id}) 泄漏了私有 marker")

    return errors


def check_attach_document_evidence(marker: str, symbol: str, owner_session_id: str) -> list[str]:
    from graph.document_evidence import attach_document_evidence
    from schemas.evidence_packet import Coverage, EvidencePacket

    packet = EvidencePacket(
        symbol=symbol,
        company_name="",
        generated_at="2026-01-01",
        as_of_date="2026-01-01",
        request_type="p4_verify",
        coverage=Coverage(),
    )
    attach_document_evidence(
        packet,
        symbol=symbol,
        query=f"{symbol} {marker}",
        k=5,
        user_session_id=owner_session_id,
    )
    if not packet.document_evidence:
        return ["attach_document_evidence 未返回任何 chunk"]
    if not any(marker in dc.content for dc in packet.document_evidence):
        return ["attach_document_evidence 结果中未包含私有 marker"]
    if not any(dc.confidence_tier == "user_submitted" for dc in packet.document_evidence if marker in dc.content):
        return ["命中 chunk 的 confidence_tier 不是 user_submitted"]
    return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 4 RAG 一键验收脚本")
    parser.add_argument("--symbol", default="TSLA", help="测试标的（默认 TSLA）")
    parser.add_argument(
        "--api-url",
        default=os.getenv("VERIFY_P4_API_URL", "http://127.0.0.1:8000"),
        help="API 根地址",
    )
    parser.add_argument("--username", default=os.getenv("VERIFY_P4_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("VERIFY_P4_PASSWORD", ""))
    parser.add_argument("--token", default=os.getenv("VERIFY_P4_TOKEN", ""))
    parser.add_argument(
        "--local",
        action="store_true",
        help="跳过 HTTP 上传，直接调用 ingest_file（无需后端）",
    )
    parser.add_argument(
        "--user-id",
        default=os.getenv("VERIFY_P4_USER_ID", "p4_verify_user"),
        help="--local 模式下的 user_session_id",
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="保留临时测试文件",
    )
    parser.add_argument(
        "--skip-workflow",
        action="store_true",
        help="跳过 attach_document_evidence 检查",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = uuid.uuid4().hex[:8]
    marker = f"ALPHAPILOT_P4_{run_id}"
    symbol = args.symbol.strip().upper()
    tmp_dir = PROJECT_ROOT / "rag_data" / "p4_verify"
    test_file: Path | None = None
    failures: list[str] = []

    print("=" * 60)
    print("AlphaPilot Phase 4 Verification")
    print(f"  symbol={symbol}  marker={marker}")
    print(f"  mode={'local ingest' if args.local else 'HTTP upload'}")
    print("=" * 60)

    try:
        _step("1/4 创建测试文件")
        test_file = create_test_file(tmp_dir, marker)
        _ok(f"已写入 {test_file}")

        _step("2/4 上传文档")
        owner_session_id = args.user_id
        if args.local:
            upload_data = upload_via_local_ingest(test_file, symbol, owner_session_id)
            _ok(f"ingest_file: {upload_data['chunks']} chunk(s), doc_id={upload_data['doc_id']}")
        else:
            token = args.token
            if not token:
                if not args.username or not args.password:
                    raise RuntimeError(
                        "HTTP 模式需要 --username/--password、VERIFY_P4_* 环境变量，或加 --local"
                    )
                token, owner_session_id = login(args.api_url, args.username, args.password)
                _ok(f"登录成功 user_id={owner_session_id}")
            else:
                owner_session_id = fetch_me(args.api_url, token)
                _ok(f"使用已有 token, user_id={owner_session_id}")

            upload_data = upload_via_api(args.api_url, token, test_file, symbol)
            _ok(
                f"POST /upload/document: {upload_data['chunks']} chunk(s), "
                f"doc_id={upload_data.get('doc_id')}"
            )

        _step("3/4 Session 隔离检索")
        iso_errors = check_session_isolation(marker, symbol, owner_session_id)
        if iso_errors:
            for err in iso_errors:
                _fail(err)
            failures.extend(iso_errors)
        else:
            _ok("无 session 不可见 / 本人可见 / 他人 session 不可见")

        _step("4/4 向量库打码与元数据")
        chunk = find_marker_chunk(marker)
        if not chunk:
            _fail("向量库中未找到含 marker 的 chunk")
            failures.append("marker chunk not found")
        else:
            meta_errors = check_redaction_and_metadata(chunk, owner_session_id)
            if meta_errors:
                for err in meta_errors:
                    _fail(err)
                failures.extend(meta_errors)
            else:
                _ok("source / tier / session / [REDACTED] 均符合预期")

        if not args.skip_workflow:
            _step("附加：attach_document_evidence 工作流")
            wf_errors = check_attach_document_evidence(marker, symbol, owner_session_id)
            if wf_errors:
                for err in wf_errors:
                    _fail(err)
                failures.extend(wf_errors)
            else:
                _ok("工作流检索到私有 chunk 且 confidence_tier=user_submitted")

    except (HTTPError, URLError, RuntimeError, OSError) as exc:
        _fail(str(exc))
        failures.append(str(exc))

    finally:
        if test_file and test_file.exists() and not args.keep_files:
            test_file.unlink(missing_ok=True)

    print("\n" + "=" * 60)
    if failures:
        print(f"P4 验收失败（{len(failures)} 项）")
        print("=" * 60)
        return 1

    print("P4 验收全部通过 ✅")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
