"""
文档上传 API。
POST /api/upload/document — 用户上传 PDF → 解析 → 分块 → 写入向量库
支持 multipart/form-data，接受文件 + 元数据字段。
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from knowledge.pdf_parser import parse_and_chunk
from rag.retriever import retriever

router = APIRouter(prefix="/api/upload", tags=["upload"])

UPLOAD_DIR = Path("rag_data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".html", ".htm", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class UploadResponse(BaseModel):
    success: bool
    doc_id: str = ""
    chunks: int = 0
    symbol: str = ""
    doc_type: str = ""
    message: str = ""


@router.post("/document", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="PDF / Word / HTML 文档"),
    symbol: str = Form(..., description="股票代码，如 0700.HK"),
    doc_type: str = Form(default="annual_report", description="文档类型: annual_report/earnings_call/research_report/news"),
    source: str = Form(default="user_uploaded", description="来源: user_uploaded/HKEX/SEC"),
    publish_date: str = Form(default="", description="发布日期，ISO date"),
    report_period: str = Form(default="", description="报告期，如 2024-12-31"),
    language: str = Form(default="zh", description="文档语言"),
    user_session_id: str = Form(default="", description="用户会话 ID（私有空间隔离）"),
):
    # ── 校验文件扩展名 ──
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}。支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # ── 保存到临时文件 ──
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{symbol}_{file_id}{ext}"
    save_path = UPLOAD_DIR / safe_name

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"文件超过大小上限 {MAX_FILE_SIZE // (1024*1024)} MB")

    save_path.write_bytes(content)

    # ── 构建元数据 ──
    now = datetime.utcnow().isoformat()
    doc_id = f"{symbol}_{doc_type}_{file_id}"
    metadata = {
        "doc_id": doc_id,
        "symbol": symbol.upper(),
        "source": source,
        "doc_type": doc_type,
        "publish_date": publish_date or now,
        "report_period": report_period or "",
        "language": language,
        "page": "",  # 解析后由 chunker 填充
    }

    # ── 解析 + 分块 ──
    try:
        chunks = parse_and_chunk(str(save_path), metadata, doc_type=doc_type)
    except Exception as exc:
        # 清理临时文件
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"文档解析失败: {exc}") from exc

    if not chunks:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="未能从文档中提取文本内容")

    # ── 写入向量库 ──
    # 用户私有空间标记
    if user_session_id:
        for c in chunks:
            c["user_session_id"] = user_session_id

    try:
        written = retriever.add_document_chunks(chunks)
    except Exception as exc:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"写入向量库失败: {exc}") from exc

    # ── 清理临时文件（成功入库后） ──
    save_path.unlink(missing_ok=True)

    return UploadResponse(
        success=True,
        doc_id=doc_id,
        chunks=written,
        symbol=symbol.upper(),
        doc_type=doc_type,
        message=f"成功导入 {written} 个文档块 ({safe_name})",
    )


__all__ = ["router"]
