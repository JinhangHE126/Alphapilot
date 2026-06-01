from typing import Any
from datetime import date

from dotenv import load_dotenv
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import HumanMessage

from graph.state import GraphState
from graph.checkpointer import get_checkpointer
from graph.user_profile import load_user_profile

from schemas.evidence_packet import (
    EvidencePacket,
    Fact,
    MissingField,
    Coverage,
    compute_evidence_score,
    determine_output_level,
    detect_conflicts,
    render_packet_for_agent,
)
from tools.data_collector import collect_all
from rag.retriever import retriever

from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from agents.strategy_agent import strategy_agent
from agents.risk_agent import risk_agent
from agents.portfolio_agent import portfolio_agent
from agents.backtesting_agent import backtesting_agent
from agents.comparison_agent import comparison_agent
from agents.recommendation_agent import recommendation_agent
from agents.portfolio_optimization_agent import portfolio_optimization_agent
from agents.alert_agent import alert_agent
from agents.guard_agent import guard_agent

load_dotenv()
checkpointer = get_checkpointer()

GUARD_MAX_RETRIES = 2

RAG_SCORE_THRESHOLD = 0.55


def evidence_packet_builder(state: GraphState) -> dict:
    """
    在 Orchestrator 路由前构造 Evidence Packet。
    1. RAG 检索（带 score）
    2. 判断冷启动条件
    3. 必要时调用外部数据工具
    4. 构造 Evidence Packet
    5. 写入 state.evidence_packet
    """
    symbol = state.get("stock_symbol", "")
    messages = state.get("messages", [])

    user_instruction = next(
        (
            m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
            for m in messages
            if (isinstance(m, dict) and m.get("role") == "user")
            or isinstance(m, HumanMessage)
        ),
        "Please perform comprehensive analysis",
    )

    today = date.today().isoformat()
    query = f"{symbol} {user_instruction[:200]}"

    rag_results = retriever.retrieve_with_scores(query, k=5)

    matched_rag = [
        r for r in rag_results
        if r.metadata.get("symbol", "").upper() == symbol.upper()
    ]
    mismatched_count = len(rag_results) - len(matched_rag)
    if mismatched_count > 0:
        print(f"   ⚠️ {mismatched_count} RAG results filtered out (symbol mismatch with {symbol})")

    is_cold_start = False
    rag_facts = []

    if matched_rag:
        top_score = matched_rag[0].score
        has_metadata = any(
            r.metadata.get("symbol") or r.metadata.get("source") for r in matched_rag
        )
        if top_score < RAG_SCORE_THRESHOLD or not has_metadata:
            is_cold_start = True
    else:
        is_cold_start = True

    if not is_cold_start:
        for r in matched_rag[:5]:
            rag_facts.append({
                "field": "rag_context",
                "value": r.doc.page_content[:300],
                "unit": "text",
                "period": "latest",
                "source": r.metadata.get("source", "rag"),
                "source_url": r.metadata.get("url"),
                "as_of_date": r.metadata.get("date", today),
                "confidence": min(r.score, 0.75),
                "confidence_tier": "llm_extracted",
            })

    collector_results = {}
    if is_cold_start:
        collector_results = collect_all(symbol)

    market_facts_raw = collector_results.get("market", []) if is_cold_start else []
    fundamental_facts_raw = collector_results.get("fundamental", []) if is_cold_start else []
    news_facts_raw = collector_results.get("news", []) if is_cold_start else []
    filings_raw = collector_results.get("filings", []) if is_cold_start else []
    hkex_raw = collector_results.get("hkex", []) if is_cold_start else []

    all_facts_raw = rag_facts + market_facts_raw + fundamental_facts_raw + news_facts_raw + filings_raw + hkex_raw

    facts = []
    for f in all_facts_raw:
        try:
            facts.append(Fact(**f))
        except Exception:
            continue

    has_fundamental = bool(fundamental_facts_raw)
    coverage = Coverage(
        rag_context="available" if rag_facts else "missing",
        market_data="available" if market_facts_raw else "missing",
        fundamental_data="available" if has_fundamental else "missing",
        news_data="available" if news_facts_raw else "missing",
        filings="missing",
    )

    expected_fields = {
        "comprehensive_analysis": ["current_price", "rsi_14", "pe_ratio", "revenue_growth_yoy", "eps_growth_yoy", "market_cap", "news_headline"],
    }
    existing_keys = {f.field for f in facts}
    missing_fields = []
    for field in expected_fields.get("comprehensive_analysis", []):
        if field not in existing_keys:
            missing_fields.append(MissingField(field=field, reason="not available from current data sources"))

    packet = EvidencePacket(
        symbol=symbol,
        company_name="",
        generated_at=today,
        as_of_date=today,
        request_type="comprehensive_analysis",
        is_cold_start=is_cold_start,
        coverage=coverage,
        facts=facts,
        missing_fields=missing_fields,
        conflicts=[],
    )
    packet = detect_conflicts(packet)
    packet = compute_evidence_score(packet)
    guard_result = determine_output_level(packet)
    packet.allowed_output_level = guard_result.allowed_output_level

    rendered = render_packet_for_agent(packet)

    print(f"\n📦 Evidence Packet Builder:")
    print(f"   Symbol: {symbol}")
    print(f"   Cold Start: {is_cold_start}")
    print(f"   RAG Results: {len(rag_results)}")
    print(f"   Facts: {len(facts)}")
    print(f"   Evidence Score: {packet.evidence_score}/100")
    print(f"   Output Level: {guard_result.allowed_output_level.value}")
    print(f"   Reason: {guard_result.reason}\n")

    return {
        "evidence_packet": packet.model_dump(),
        "cold_start": is_cold_start,
        "messages": [{"role": "system", "content": rendered}],
    }


def orchestrator_node(state: GraphState) -> dict:
    """智能 Orchestrator - 支持实时警报模式"""
    messages = state.get("messages", [])
    executed = state.get("executed_agents", [])
    stock_symbol = state.get("stock_symbol", "TSLA")

    user_instruction = next(
        (
            m.get("content", "")
            if isinstance(m, dict)
            else getattr(m, "content", "")
            for m in messages
            if (isinstance(m, dict) and m.get("role") == "user")
            or isinstance(m, HumanMessage)
        ),
        "Please perform comprehensive analysis",
    )

    lower_instruction = user_instruction.lower()

    is_alert = any(
        keyword in lower_instruction
        for keyword in [
            "警报", "alert", "监控", "monitor", "通知", "提醒",
            "价格突破", "价格跌破", "rsi", "macd", "触发"
        ]
    )

    is_optimization = any(
        keyword in lower_instruction
        for keyword in [
            "优化", "optimization", "组合优化", "资产配置",
            "权重", "portfolio optimization", "sharpe ratio"
        ]
    )

    is_comprehensive = any(
        keyword in lower_instruction
        for keyword in [
            "全面", "完整", "complete", "comprehensive",
            "full analysis", "全方位", "全部", "所有"
        ]
    )

    is_personalized = any(
        keyword in lower_instruction
        for keyword in [
            "个性化", "personalized", "我的", "向我", "为我",
            "投资计划", "投资建议", "仓位建议", "风险偏好",
            "保守型", "中线持有", "我的偏好"
        ]
    )

    _alert_done = any(
        getattr(m, "name", None) == "alert_agent"
        for m in messages
        if not isinstance(m, dict)
    )
    _optimization_done = any(
        getattr(m, "name", None) == "portfolio_optimization_agent"
        for m in messages
        if not isinstance(m, dict)
    )
    _recommendation_done = any(
        getattr(m, "name", None) == "recommendation_agent"
        for m in messages
        if not isinstance(m, dict)
    )

    guard_check = state.get("guard_check", {})
    guard_retry = state.get("guard_retry_count", 0)
    guard_failed = bool(guard_check) and not guard_check.get("is_valid") and guard_retry < GUARD_MAX_RETRIES

    if guard_failed:
        corrections = guard_check.get("corrections", [])
        correction_msg = "\n".join(f"- {c}" for c in corrections) if corrections else "Address the identified issues."
        guard_msg = {"role": "user", "content": f"Guard Agent identified issues:\n{correction_msg}\nPlease fix these and regenerate your analysis."}
        messages.append(guard_msg)
        next_agents = ["strategy_expert"]
        executed = [a for a in executed if a not in ("strategy_expert", "risk_expert", "recommendation_agent", "guard_agent")]
        reasoning = f"Guard check failed (retry {guard_retry}/{GUARD_MAX_RETRIES}). Re-running strategy → risk → recommendation."
    elif is_alert:
        if _alert_done:
            next_agents = []
            reasoning = "Alert agent completed. Ending workflow."
        else:
            next_agents = ["alert_agent"]
            reasoning = "User requested real-time alert / monitoring → route to alert_agent"
    elif is_optimization:
        if _optimization_done:
            next_agents = []
            reasoning = "Portfolio optimization agent completed. Ending workflow."
        else:
            next_agents = ["portfolio_optimization_agent"]
            reasoning = "User requested portfolio optimization → route to portfolio_optimization_agent"
    elif is_personalized and not is_comprehensive:
        if _recommendation_done:
            next_agents = []
            reasoning = "Recommendation agent completed. Ending workflow."
        else:
            next_agents = ["recommendation_agent"]
            reasoning = "User requested personalized recommendation → route to recommendation_agent"
    else:
        FULL_STAGES = [
            ["market_data_expert", "fundamental_expert", "news_sentiment_expert"],
            ["strategy_expert"],
            ["risk_expert"],
            ["portfolio_agent"],
            ["backtesting_agent"],
        ]
        executed_set = set(executed)
        next_agents = []
        for stage in FULL_STAGES:
            missing = [agent for agent in stage if agent not in executed_set]
            if missing:
                next_agents = missing
                break

        stage0_agents = {"market_data_expert", "fundamental_expert", "news_sentiment_expert"}
        stage0_done = stage0_agents.issubset(executed_set)
        if stage0_done and next_agents == ["strategy_expert"]:
            ep = state.get("evidence_packet", {})
            evidence_score = ep.get("evidence_score", 0) if ep else 0
            if evidence_score < 50 and "guard_agent" not in executed_set:
                next_agents = ["guard_agent"]
                reasoning = (
                    f"Evidence score {evidence_score}/100 < 50 after data collection. "
                    f"Skipping strategy→risk→portfolio→backtest→recommendation. Routing to Guard."
                )

        if not next_agents and "recommendation_agent" not in executed_set:
            next_agents = ["recommendation_agent"]
            reasoning = "Full analysis done. Routing to recommendation for personalized advice."
        elif not next_agents and "recommendation_agent" in executed_set and "guard_agent" not in executed_set:
            next_agents = ["guard_agent"]
            reasoning = "Recommendation complete. Routing to Guard Agent for fact-check verification."
        elif not next_agents:
            reasoning = "Guard verification passed. Analysis pipeline complete."
        else:
            reasoning = "Deterministic full-analysis route."

    print("\n🎛️ Orchestrator Decision:")
    print(f"   User Instruction: {user_instruction[:80]}...")
    print(f"   Executed: {executed}")
    print(f"   Next: {next_agents}")
    print(f"   Reasoning: {reasoning}\n")

    if not next_agents:
        return {"next": "__end__", "orchestrator_reasoning": reasoning}

    result = {
        "next": next_agents,
        "executed_agents": executed + next_agents,
        "orchestrator_reasoning": reasoning,
    }
    if guard_failed:
        result["guard_check"] = {}
    return result
# ====================== StateGraph ======================
workflow = StateGraph(GraphState)

workflow.add_node("market_data_expert", market_agent)
workflow.add_node("fundamental_expert", fundamental_agent)
workflow.add_node("news_sentiment_expert", news_agent)
workflow.add_node("strategy_expert", strategy_agent)
workflow.add_node("risk_expert", risk_agent)
workflow.add_node("portfolio_agent", portfolio_agent)
workflow.add_node("backtesting_agent", backtesting_agent)
workflow.add_node("comparison_agent", comparison_agent)
workflow.add_node("alert_agent", alert_agent)
workflow.add_node("recommendation_agent", recommendation_agent)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("portfolio_optimization_agent", portfolio_optimization_agent)
workflow.add_node("guard_agent", guard_agent)

workflow.add_node("evidence_packet_builder", evidence_packet_builder)

workflow.add_edge(START, "evidence_packet_builder")
workflow.add_edge("evidence_packet_builder", "orchestrator")

workflow.add_conditional_edges(
    "orchestrator",
    lambda state: state.get("next", "__end__"),
    {
        "market_data_expert": "market_data_expert",
        "fundamental_expert": "fundamental_expert",
        "news_sentiment_expert": "news_sentiment_expert",
        "strategy_expert": "strategy_expert",
        "risk_expert": "risk_expert",
        "portfolio_agent": "portfolio_agent",
        "backtesting_agent": "backtesting_agent",
        "comparison_agent": "comparison_agent",
        "alert_agent": "alert_agent",
        "recommendation_agent": "recommendation_agent",
        "portfolio_optimization_agent": "portfolio_optimization_agent",
        "guard_agent": "guard_agent",
        "__end__": END,
    },
)

for agent in [
    "market_data_expert",
    "fundamental_expert",
    "news_sentiment_expert",
    "strategy_expert",
    "risk_expert",
    "portfolio_agent",
    "backtesting_agent",
    "alert_agent",
    "comparison_agent",
    "portfolio_optimization_agent",
    "recommendation_agent",
]:
    workflow.add_edge(agent, "orchestrator")

workflow.add_conditional_edges(
    "guard_agent",
    lambda state: (
        "__end__"
        if state.get("guard_check", {}).get("is_valid")
        or state.get("guard_retry_count", 0) >= GUARD_MAX_RETRIES
        else "orchestrator"
    ),
    {
        "orchestrator": "orchestrator",
        "__end__": END,
    },
)

app = workflow.compile(checkpointer=checkpointer)

__all__ = ["app"]