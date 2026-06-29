import sqlite3
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
import os
import time
import uuid
import logging

import jwt
import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from api.response import error, success
from db.models import init_db
from db.repository import (
    add_analysis_event,
    add_message,
    authenticate_user,
    complete_analysis_record,
    create_analysis_record,
    create_session,
    create_user,
    delete_analysis_record,
    get_analysis_citations,
    get_analysis_detail,
    get_analysis_events,
    get_session,
    get_user_stats,
    list_analysis_history,
    list_messages,
    list_sessions,
    save_analysis_citations,
)
from graph.state import GraphState
from graph.user_profile import load_user_profile, save_user_profile
from services.auth_service import create_access_token, decode_access_token
from api.upload import router as upload_router

JWT_SECRET = os.getenv("JWT_SECRET", "change_this_in_prod")
auth_scheme = HTTPBearer()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger("alphapilot.api")
allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",") if origin.strip()]

# ====================== FastAPI 应用 ======================
api = FastAPI(
    title="AlphaPilot API",
    description="多智能体股票投资分析平台 API",
    version="1.0.0"
)

# CORS 支持（允许前端调用）
api.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api.include_router(upload_router)

@api.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started = time.time()
    response = await call_next(request)
    elapsed_ms = int((time.time() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request path=%s method=%s status=%s request_id=%s duration_ms=%s",
        request.url.path,
        request.method,
        response.status_code,
        request_id,
        elapsed_ms,
    )
    return response

@api.on_event("startup")
def startup_event() -> None:
    init_db()
    try:
        from knowledge.pdf_env import log_pdf_capabilities
        log_pdf_capabilities()
    except Exception as exc:
        print(f"⚠️ PDF capability check skipped: {exc}")
    try:
        from knowledge.scheduler import start_document_scheduler
        start_document_scheduler()
    except Exception as exc:
        print(f"⚠️ Document scheduler skipped: {exc}")


@api.on_event("shutdown")
def shutdown_event() -> None:
    try:
        from knowledge.scheduler import stop_document_scheduler
        stop_document_scheduler()
    except Exception:
        pass


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> dict[str, Any]:
    token = credentials.credentials
    try:
        payload = decode_access_token(token, JWT_SECRET)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    return {
        "id": int(payload["sub"]),
        "username": payload.get("username", ""),
    }


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AnalyzeRequest(BaseModel):
    message: str
    stock_symbol: Optional[str] = "TSLA"
    session_id: Optional[str] = None

class AnalyzeStreamRequest(BaseModel):
    message: str
    stock_symbol: Optional[str] = "TSLA"
    session_id: Optional[str] = None
    language: Optional[str] = None

class CompareRequest(BaseModel):
    stock_symbols: List[str] = ["TSLA", "NVDA"]

class CompareStreamRequest(BaseModel):
    stock_symbols: List[str] = ["TSLA", "NVDA"]

class BacktestRequest(BaseModel):
    stock_symbol: str = "TSLA"
    strategy_desc: Optional[str] = ""

class AlertRequest(BaseModel):
    stock_symbol: str = "TSLA"
    condition: Optional[str] = ""

class OptimizeRequest(BaseModel):
    stock_symbols: List[str] = ["TSLA", "NVDA", "AAPL"]
    risk_preference: Optional[str] = "medium"

class ProfileUpdateRequest(BaseModel):
    risk_preference: Optional[str] = None
    horizon: Optional[str] = None
    display_name: Optional[str] = None

class SessionCreateRequest(BaseModel):
    title: Optional[str] = "New Session"


@api.post("/auth/register")
async def register(request: RegisterRequest):
    try:
        user = create_user(request.username, request.password)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Username already exists") from exc
    token = create_access_token(user, JWT_SECRET)
    return success({"user_id": user["id"], "username": user["username"], "access_token": token, "token_type": "bearer"})


@api.post("/auth/login")
async def login(request: LoginRequest):
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user, JWT_SECRET)
    return success({"access_token": token, "token_type": "bearer", "user_id": user["id"], "username": user["username"]})


@api.post("/auth/refresh")
async def refresh_token(current_user: dict[str, Any] = Depends(get_current_user)):
    token = create_access_token(current_user, JWT_SECRET)
    return success({"access_token": token, "token_type": "bearer"})


@api.get("/auth/me")
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)):
    return success({"id": current_user["id"], "username": current_user["username"]})


@api.post("/sessions")
async def create_user_session(
    request: SessionCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = create_session(current_user["id"], title=request.title or "New Session")
    return success(session)


@api.get("/sessions")
async def get_user_sessions(current_user: dict[str, Any] = Depends(get_current_user)):
    return success(list_sessions(current_user["id"]))


@api.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    session = get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = list_messages(session_id, current_user["id"])
    return success({"session": session, "messages": messages})


@api.post("/analyze")
async def analyze(request: AnalyzeRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    """核心分析接口"""
    from services.analysis_service import run_analysis_once

    session = None
    if request.session_id:
        session = get_session(request.session_id, current_user["id"])
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = create_session(current_user["id"], title=request.message[:60] or "New Session")
    session_id = session["id"]
    thread_id = f"user_{current_user['id']}_{session_id}"

    add_message(session_id, "user", request.message, node_name="user_input")
    analysis_record = create_analysis_record(
        current_user["id"],
        request.stock_symbol or "TSLA",
        analysis_type="analyze",
    )
    analysis_id = analysis_record["id"]
    result = run_analysis_once(
        user_message=request.message,
        stock_symbol=request.stock_symbol or "TSLA",
        user_id=str(current_user["id"]),
        thread_id=thread_id,
    )
    add_message(session_id, "assistant", result["final_report"], node_name="recommendation_agent")
    guard = result.get("guard_check")
    final_score = float(guard.get("confidence_score", 0)) if isinstance(guard, dict) else 0.0
    complete_analysis_record(
        analysis_id,
        report=result["final_report"],
        recommendation=result.get("recommendation"),
        final_score=final_score,
        status="completed",
    )
    # 3.3.2 — 同步路径也写 citations
    citations = result.get("citations", {})
    if citations and isinstance(citations, dict):
        save_analysis_citations(
            analysis_id=analysis_id,
            chunk_ids=citations.get("chunk_ids", []),
            doc_markers=citations.get("doc_markers"),
            evidence_snapshot=citations.get("evidence_snapshot"),
        )

    return success({
        "session_id": session_id,
        "stock_symbol": request.stock_symbol or "TSLA",
        "report": result["final_report"],
        "recommendation": result["recommendation"],
    })

@api.post("/analyze/stream")
async def analyze_stream(request: AnalyzeStreamRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import stream_analysis_events

    session = None
    if request.session_id:
        session = get_session(request.session_id, current_user["id"])
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = create_session(current_user["id"], title=request.message[:60] or "New Session")
    session_id = session["id"]
    thread_id = f"user_{current_user['id']}_{session_id}"

    add_message(session_id, "user", request.message, node_name="user_input")
    analysis_record = create_analysis_record(
        current_user["id"],
        request.stock_symbol or "TSLA",
        analysis_type="analyze",
    )
    analysis_id = analysis_record["id"]

    def event_generator():
        final_payload = {"final_report": "分析完成", "recommendation": None}
        seq_num = 0
        stream = stream_analysis_events(
            user_message=request.message,
            stock_symbol=request.stock_symbol or "TSLA",
            user_id=str(current_user["id"]),
            thread_id=thread_id,
            session_id=session_id,
            language=request.language,
        )
        while True:
            try:
                event = next(stream)
                seq_num += 1
                lines = event.strip().split("\n")
                event_line = next((l for l in lines if l.startswith("event: ")), "")
                data_line = next((l for l in lines if l.startswith("data: ")), "")
                event_type = event_line.replace("event: ", "", 1).strip()
                data_str = data_line.replace("data: ", "", 1).strip()
                try:
                    data_obj = json.loads(data_str)
                except (json.JSONDecodeError, ValueError):
                    data_obj = {}

                if event_type == "analysis_complete":
                    final_payload = data_obj
                elif event_type in ("agent_start", "agent_done"):
                    add_analysis_event(analysis_id, seq_num, data_obj.get("agent", ""), event_type)
                elif event_type == "agent_output":
                    add_analysis_event(
                        analysis_id, seq_num,
                        data_obj.get("agent", ""), event_type,
                        content=data_obj.get("content", ""),
                    )
                elif event_type == "error":
                    add_analysis_event(analysis_id, seq_num, "system", "error", content=data_obj.get("detail", ""))

                yield event
            except StopIteration as stop:
                if isinstance(stop.value, dict):
                    final_payload = stop.value
                break
            except Exception as exc:
                complete_analysis_record(
                    analysis_id,
                    report="",
                    status="failed",
                )
                yield f"event: error\ndata: {{\"detail\": \"{str(exc)}\"}}\n\n"
                break

        add_message(
            session_id,
            "assistant",
            final_payload.get("final_report", "分析完成"),
            node_name="recommendation_agent",
        )
        guard = final_payload.get("guard_check")
        final_score = float(guard.get("confidence_score", 0)) if isinstance(guard, dict) else 0.0
        complete_analysis_record(
            analysis_id,
            report=final_payload.get("final_report", ""),
            recommendation=final_payload.get("recommendation"),
            final_score=final_score,
            status="completed",
        )
        # 3.3.2 — 写入 citations（每次完成的分析均记录引用的 chunk）
        citations = final_payload.get("citations", {})
        if citations and isinstance(citations, dict):
            save_analysis_citations(
                analysis_id=analysis_id,
                chunk_ids=citations.get("chunk_ids", []),
                doc_markers=citations.get("doc_markers"),
                evidence_snapshot=citations.get("evidence_snapshot"),
            )

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@api.post("/compare")
async def compare(request: CompareRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import run_comparison_once

    result = run_comparison_once(request.stock_symbols, str(current_user["id"]))
    return success(result)


@api.post("/compare/stream")
async def compare_stream(request: CompareStreamRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import stream_analysis_events

    message = f"请对比分析以下股票: {', '.join(request.stock_symbols)}"

    def event_generator():
        for event in stream_analysis_events(
            user_message=message,
            stock_symbol=request.stock_symbols[0],
            user_id=str(current_user["id"]),
            thread_id=f"compare_{current_user['id']}",
            session_id="",
        ):
            yield event

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

@api.post("/backtest")
async def backtest(request: BacktestRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import run_backtest_once

    result = run_backtest_once(request.stock_symbol, request.strategy_desc or "", str(current_user["id"]))
    return success(result)


@api.post("/backtest/stream")
async def backtest_stream(request: BacktestRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import stream_analysis_events

    desc = request.strategy_desc or f"对 {request.stock_symbol} 的策略进行历史回测"
    message = f"请对 {request.stock_symbol} 进行历史回测分析。策略描述: {desc}"

    def event_generator():
        for event in stream_analysis_events(
            user_message=message,
            stock_symbol=request.stock_symbol,
            user_id=str(current_user["id"]),
            thread_id=f"backtest_{current_user['id']}",
            session_id="",
        ):
            yield event

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

@api.post("/alert")
async def alert(request: AlertRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import run_alert_once

    result = run_alert_once(request.stock_symbol, request.condition or "", str(current_user["id"]))
    return success(result)


@api.post("/alert/stream")
async def alert_stream(request: AlertRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import stream_analysis_events

    cond = request.condition or f"监控 {request.stock_symbol} 的价格、RSI、MACD 等关键技术指标"
    message = f"请对 {request.stock_symbol} 进行实时监控。触发条件: {cond}"

    def event_generator():
        for event in stream_analysis_events(
            user_message=message,
            stock_symbol=request.stock_symbol,
            user_id=str(current_user["id"]),
            thread_id=f"alert_{current_user['id']}",
            session_id="",
        ):
            yield event

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

@api.post("/optimize")
async def optimize(request: OptimizeRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import run_optimize_once

    result = run_optimize_once(request.stock_symbols, request.risk_preference or "medium", str(current_user["id"]))
    return success(result)


@api.post("/optimize/stream")
async def optimize_stream(request: OptimizeRequest, current_user: dict[str, Any] = Depends(get_current_user)):
    from services.analysis_service import stream_analysis_events

    symbols_str = ", ".join(request.stock_symbols)
    message = f"请对以下投资组合进行优化: {symbols_str}。风险偏好: {request.risk_preference or 'medium'}"

    def event_generator():
        for event in stream_analysis_events(
            user_message=message,
            stock_symbol=request.stock_symbols[0],
            user_id=str(current_user["id"]),
            thread_id=f"optimize_{current_user['id']}",
            session_id="",
        ):
            yield event

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


# ====================== 文档上传 ======================

@api.post("/upload/document")
async def upload_document(
    file: UploadFile = File(..., description="PDF / Word / HTML 文档"),
    symbol: str = Form(..., description="股票代码，如 0700.HK"),
    doc_type: str = Form(default="annual_report", description="annual_report/earnings_call/research_report/news"),
    source: str = Form(default="user_uploaded", description="HKEX / SEC / user_uploaded"),
    publish_date: str = Form(default=""),
    report_period: str = Form(default=""),
    language: str = Form(default="zh"),
    consent_at: str = Form(default="", description="用户确认上传内容合规的时间戳 (ISO 8601)"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    from knowledge.document_ingest import ingest_file
    from knowledge.pdf_env import require_text_extraction

    UPLOAD_DIR = Path("rag_data/uploads")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".html", ".htm", ".txt"}

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, detail=f"不支持的文件类型: {ext}")

    if ext == ".pdf":
        try:
            require_text_extraction()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{symbol}_{file_id}{ext}"
    save_path = UPLOAD_DIR / safe_name
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, detail="文件超过 50 MB 上限")
    save_path.write_bytes(content)

    now = datetime.utcnow().isoformat()
    doc_id = f"{symbol}_{doc_type}_{file_id}"
    user_session_id = str(current_user.get("id", ""))
    metadata = {
        "doc_id": doc_id,
        "symbol": symbol.upper(),
        "source": "user_uploaded",
        "doc_type": doc_type,
        "publish_date": publish_date or now,
        "report_period": report_period or "",
        "language": language,
        "page": "",
        "consent_at": consent_at or now,
    }

    # 记录上传合规审计日志
    if consent_at:
        print(f"[upload] consent_at={consent_at} user={user_session_id} symbol={symbol.upper()} doc_type={doc_type} file={safe_name}")

    try:
        written = ingest_file(
            str(save_path),
            metadata,
            doc_type=doc_type,
            user_session_id=user_session_id,
        )
    except Exception as exc:
        save_path.unlink(missing_ok=True)
        raise HTTPException(422, detail=f"文档解析失败: {exc}") from exc

    if not written:
        save_path.unlink(missing_ok=True)
        raise HTTPException(422, detail="未能从文档中提取文本内容")

    save_path.unlink(missing_ok=True)

    return {
        "data": {
            "doc_id": doc_id,
            "chunks": written,
            "symbol": symbol.upper(),
            "doc_type": doc_type,
            "message": f"成功导入 {written} 个文档块 ({safe_name})",
        },
        "status": "ok",
    }


@api.get("/history")
async def get_history(
    page: int = 1,
    page_size: int = 20,
    stock_symbol: Optional[str] = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    items, total = list_analysis_history(
        current_user["id"],
        page=page,
        page_size=page_size,
        stock_symbol=stock_symbol,
    )
    return success({"items": items, "total": total, "page": page, "page_size": page_size})


@api.get("/history/{analysis_id}")
async def get_history_detail(analysis_id: int, current_user: dict[str, Any] = Depends(get_current_user)):
    record = get_analysis_detail(analysis_id, current_user["id"])
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    events = get_analysis_events(analysis_id)
    citations = get_analysis_citations(analysis_id)
    return success({"id": analysis_id, **record, "events": events, "citations": citations})


@api.delete("/history/{analysis_id}")
async def delete_history(analysis_id: int, current_user: dict[str, Any] = Depends(get_current_user)):
    if not delete_analysis_record(analysis_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    return success(message="deleted")


@api.get("/profile")
async def get_profile(current_user: dict[str, Any] = Depends(get_current_user)):
    profile = load_user_profile(str(current_user["id"]))
    return success({"user_id": current_user["id"], **profile})

@api.put("/profile")
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    profile = load_user_profile(str(current_user["id"]))
    if request.risk_preference is not None:
        profile["risk_preference"] = request.risk_preference
    if request.horizon is not None:
        profile["horizon"] = request.horizon
    if request.display_name is not None:
        profile["display_name"] = request.display_name
    save_user_profile(str(current_user["id"]), profile)
    return success({"user_id": current_user["id"], **profile})

@api.get("/dashboard/stats")
async def dashboard_stats(current_user: dict[str, Any] = Depends(get_current_user)):
    stats = get_user_stats(current_user["id"])
    recent_items, _ = list_analysis_history(current_user["id"], page=1, page_size=5)
    return success({"stats": stats, "recent_analyses": recent_items})


@api.get("/metrics")
async def prometheus_metrics():
    from monitoring.counters import get_metrics
    m = get_metrics()
    return {"data": m.snapshot(), "status": "ok"}


@api.get("/analyze/stream")
async def analyze_stream_get(
    message: str,
    stock_symbol: str = "TSLA",
    session_id: Optional[str] = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    from services.analysis_service import stream_analysis_events

    if session_id:
        session = get_session(session_id, current_user["id"])
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = create_session(current_user["id"], title=message[:60] or "New Session")
        session_id = session["id"]

    def event_generator():
        for event in stream_analysis_events(
            user_message=message,
            stock_symbol=stock_symbol,
            user_id=str(current_user["id"]),
            thread_id=f"user_{current_user['id']}_{session_id}",
            session_id=session_id,
        ):
            yield event

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@api.get("/")
async def root():
    return {
        "service": "AlphaPilot API",
        "version": "1.0.0",
        "description": "多智能体股票投资分析平台 API",
        "endpoints": {
            "health": "GET /health",
            "register": "POST /auth/register",
            "login": "POST /auth/login",
            "sessions": "GET/POST /sessions",
            "session_messages": "GET /sessions/{session_id}/messages",
            "analyze": "POST /analyze",
            "analyze_stream": "POST /analyze/stream",
            "compare": "POST /compare",
            "backtest": "POST /backtest",
            "alert": "POST /alert",
            "optimize": "POST /optimize"
        }
    }

@api.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AlphaPilot API"}

# ====================== 启动 ======================
if __name__ == "__main__":
    uvicorn.run(
        "api.main:api",
        host="0.0.0.0",
        port=8000,
        reload=True
    )