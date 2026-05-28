import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import os

from graph.workflow import app as langgraph_app
from graph.state import GraphState
from graph.user_profile import load_user_profile
from agents.comparison_agent import comparison_agent
from agents.backtesting_agent import backtesting_agent
from agents.alert_agent import alert_agent
from agents.portfolio_optimization_agent import portfolio_optimization_agent

# ====================== FastAPI 应用 ======================
api = FastAPI(
    title="AlphaPilot API",
    description="多智能体股票投资分析平台 API",
    version="1.0.0"
)

# CORS 支持（允许前端调用）
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    message: str
    stock_symbol: Optional[str] = "TSLA"
    user_id: Optional[str] = "default"

class CompareRequest(BaseModel):
    stock_symbols: List[str] = ["TSLA", "NVDA"]
    user_id: Optional[str] = "default"

class BacktestRequest(BaseModel):
    stock_symbol: str = "TSLA"
    strategy_desc: Optional[str] = ""
    user_id: Optional[str] = "default"

class AlertRequest(BaseModel):
    stock_symbol: str = "TSLA"
    condition: Optional[str] = ""
    user_id: Optional[str] = "default"

class OptimizeRequest(BaseModel):
    stock_symbols: List[str] = ["TSLA", "NVDA", "AAPL"]
    risk_preference: Optional[str] = "medium"
    user_id: Optional[str] = "default"

@api.post("/analyze")
async def analyze(request: AnalyzeRequest):
    """核心分析接口"""
    initial_state = {
        "stock_symbol": request.stock_symbol,
        "messages": [{"role": "user", "content": request.message}],
    }

    config = {"configurable": {"thread_id": f"api_{request.user_id}_{os.urandom(4).hex()}"}}

    result = {}
    for chunk in langgraph_app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if "final_report" in update and update.get("final_report"):
                result["final_report"] = update["final_report"]
            if node_name == "recommendation_agent" and update.get("messages"):
                result["recommendation"] = update["messages"][-1].content if hasattr(update["messages"][-1], "content") else str(update["messages"][-1])

    return {
        "status": "success",
        "stock_symbol": request.stock_symbol,
        "report": result.get("final_report", "分析完成"),
        "recommendation": result.get("recommendation")
    }

@api.post("/compare")
async def compare(request: CompareRequest):
    symbols_str = ", ".join(request.stock_symbols)
    message = f"请对比分析以下股票: {symbols_str}，包括技术面、基本面、新闻情绪和投资建议的全面对比"

    initial_state: GraphState = {
        "stock_symbol": request.stock_symbols[0],
        "messages": [{"role": "user", "content": message}],
        "user_profile": load_user_profile(request.user_id),
    }

    result = comparison_agent(initial_state)
    messages = result.get("messages", [])
    content = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1]) if messages else "对比分析完成"

    return {
        "status": "success",
        "stock_symbols": request.stock_symbols,
        "comparison_report": content
    }

@api.post("/backtest")
async def backtest(request: BacktestRequest):
    desc = request.strategy_desc or f"对 {request.stock_symbol} 的策略进行历史回测"
    message = f"请对 {request.stock_symbol} 进行历史回测分析。策略描述: {desc}。请输出总收益、年化收益、夏普比率、最大回撤、胜率等关键指标"

    initial_state: GraphState = {
        "stock_symbol": request.stock_symbol,
        "messages": [{"role": "user", "content": message}],
    }

    result = backtesting_agent(initial_state)
    messages = result.get("messages", [])
    content = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1]) if messages else "回测分析完成"

    return {
        "status": "success",
        "stock_symbol": request.stock_symbol,
        "backtest_report": content
    }

@api.post("/alert")
async def alert(request: AlertRequest):
    cond = request.condition or f"监控 {request.stock_symbol} 的价格、RSI、MACD 等关键技术指标，如有异常请触发警报"
    message = f"请对 {request.stock_symbol} 进行实时监控。触发条件: {cond}"

    initial_state: GraphState = {
        "stock_symbol": request.stock_symbol,
        "messages": [{"role": "user", "content": message}],
    }

    result = alert_agent(initial_state)
    messages = result.get("messages", [])
    content = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1]) if messages else "警报分析完成"

    return {
        "status": "success",
        "stock_symbol": request.stock_symbol,
        "alert_report": content
    }

@api.post("/optimize")
async def optimize(request: OptimizeRequest):
    symbols_str = ", ".join(request.stock_symbols)
    message = f"请对以下投资组合进行优化: {symbols_str}。风险偏好: {request.risk_preference}"

    user_profile = load_user_profile(request.user_id)
    user_profile["risk_preference"] = request.risk_preference

    initial_state: GraphState = {
        "stock_symbol": request.stock_symbols[0],
        "messages": [{"role": "user", "content": message}],
        "user_profile": user_profile,
    }

    result = portfolio_optimization_agent(initial_state)
    messages = result.get("messages", [])
    content = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1]) if messages else "组合优化完成"

    return {
        "status": "success",
        "stock_symbols": request.stock_symbols,
        "risk_preference": request.risk_preference,
        "optimization_report": content
    }

@api.get("/")
async def root():
    return {
        "service": "AlphaPilot API",
        "version": "1.0.0",
        "description": "多智能体股票投资分析平台 API",
        "endpoints": {
            "health": "GET /health",
            "analyze": "POST /analyze",
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