from typing import Any
from datetime import date
import time

from dotenv import load_dotenv
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import HumanMessage

from graph.state import GraphState
from graph.checkpointer import get_checkpointer
from graph.user_profile import load_user_profile
from monitoring.counters import get_metrics

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
from knowledge.ingest_service import upsert_packet
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

RAG_SIMILARITY_THRESHOLD = 0.55


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
    fact_store_hit = False

    from db.fact_store import get_fact_store
    store = get_fact_store()
    if store.has_coverage(symbol, ["current_price"]):
        stored_active = store.get_active_facts(symbol)
        if len(stored_active) >= 3:
            fact_store_hit = True
            is_cold_start = False
            print(f"   📦 Fact Store hit: {len(stored_active)} active facts for {symbol}, skipping cold start")
    if not fact_store_hit and matched_rag:
        top_similarity = matched_rag[0].similarity
        has_metadata = any(
            r.metadata.get("symbol") or r.metadata.get("source") for r in matched_rag
        )
        if top_similarity < RAG_SIMILARITY_THRESHOLD or not has_metadata:
            is_cold_start = True
    elif not fact_store_hit:
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
                "confidence": min(r.similarity, 0.95),
                "confidence_tier": "llm_extracted",
            })

    stored_fact_dicts = []
    collector_results = {}
    if is_cold_start:
        collector_results = collect_all(symbol)
    elif fact_store_hit:
        stored_facts = store.get_active_facts(symbol)
        for sf in stored_facts:
            tier = sf.get("confidence_tier", "machine")
            stored_fact_dicts.append({
                "field": sf["field"],
                "value": sf["value"],
                "unit": sf["unit"],
                "period": sf["period"],
                "source": sf["source"],
                "source_url": sf.get("source_url"),
                "as_of_date": sf["as_of_date"],
                "confidence": sf["confidence"],
                "confidence_tier": tier,
            })
        print(f"   📦 Fact Store: {len(stored_facts)} active facts loaded for {symbol}")

    use_collector = is_cold_start
    market_facts_raw = collector_results.get("market", []) if use_collector else []
    fundamental_facts_raw = collector_results.get("fundamental", []) if use_collector else []
    news_facts_raw = collector_results.get("news", []) if use_collector else []
    filings_raw = collector_results.get("filings", []) if use_collector else []
    hkex_raw = collector_results.get("hkex", []) if use_collector else []

    all_collectors_failed = (
        is_cold_start
        and not market_facts_raw
        and not fundamental_facts_raw
        and not news_facts_raw
        and not filings_raw
        and not hkex_raw
    )

    if all_collectors_failed:
        if rag_facts:
            print(f"   🛟 ESCAPE POD (DEGRADE): All collectors failed, falling back to RAG-only for {symbol}")
            all_facts_raw = rag_facts
            is_cold_start = False
        else:
            print(f"   🛟 ESCAPE POD (REJECT): All collectors failed + no RAG, rejecting {symbol}")
            escape_packet = EvidencePacket(
                symbol=symbol,
                company_name="",
                generated_at=today,
                as_of_date=today,
                request_type="comprehensive_analysis",
                is_cold_start=True,
                coverage=Coverage(
                    rag_context="missing",
                    market_data="missing",
                    fundamental_data="missing",
                    news_data="missing",
                    filings="missing",
                ),
                facts=[],
                missing_fields=[
                    MissingField(field="all", reason="external data sources unavailable, no RAG cache命中")
                ],
                conflicts=[],
                evidence_score=0,
                allowed_output_level="insufficient_evidence",
            )
            return {
                "evidence_packet": escape_packet.model_dump(mode="json"),
                "cold_start": True,
                "messages": [{
                    "role": "system",
                    "content": (
                        f"## ESCAPE POD: Data Unavailable\n\n"
                        f"当前无法获取 {symbol} 的任何数据。"
                        f"所有外部数据源（市场、基本面、新闻、监管披露）均不可用，"
                        f"且知识库中无历史缓存。\n\n"
                        f"请稍后重试，或提供本地资料（PDF 财报、公告链接等）。"
                    ),
                }],
            }
    elif fact_store_hit:
        all_facts_raw = rag_facts + stored_fact_dicts
    else:
        all_facts_raw = rag_facts + market_facts_raw + fundamental_facts_raw + news_facts_raw + filings_raw + hkex_raw

    facts = []
    for f in all_facts_raw:
        try:
            facts.append(Fact(**f))
        except Exception:
            continue

    has_fundamental = bool(fundamental_facts_raw) or (
        fact_store_hit and any(
            f.field in ("pe_ratio", "market_cap", "revenue_growth_yoy", "eps_growth_yoy", "revenue", "eps")
            for f in facts
        )
    )
    coverage = Coverage(
        rag_context="available" if rag_facts else "missing",
        market_data="available" if (market_facts_raw or fact_store_hit) else "missing",
        fundamental_data="available" if has_fundamental else "missing",
        news_data="available" if (news_facts_raw or fact_store_hit) else "missing",
        filings="available" if (filings_raw or fact_store_hit) else "missing",
    )

    expected_fields = {
        "comprehensive_analysis": [
            "current_price", "rsi_14", "pe_ratio",
            "revenue_growth_yoy", "eps_growth_yoy", "market_cap", "news_headline",
        ],
    }

    FIELD_SUBSTITUTES = {
        "revenue_growth_yoy": ["revenue", "revenue_ttm"],
        "eps_growth_yoy": ["eps", "eps_diluted"],
    }

    existing_keys = {f.field for f in facts}
    missing_fields = []
    for field in expected_fields.get("comprehensive_analysis", []):
        if field in existing_keys:
            continue
        substitutes = FIELD_SUBSTITUTES.get(field, [])
        found_sub = None
        for sub in substitutes:
            if sub in existing_keys:
                found_sub = sub
                break
        if found_sub:
            missing_fields.append(MissingField(
                field=field,
                reason=f"not directly available; using '{found_sub}' as partial substitute",
                substitute=found_sub,
            ))
        else:
            missing_fields.append(MissingField(
                field=field,
                reason="not available from current data sources",
            ))

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
    ingestion_result = None
    try:
        ingestion_result = upsert_packet(packet)
    except Exception as exc:
        ingestion_result = {"symbol": symbol, "ingested": 0, "skipped": -1, "error": str(exc)}

    rendered = render_packet_for_agent(packet)

    print(f"\n📦 Evidence Packet Builder:")
    print(f"   Symbol: {symbol}")
    print(f"   Cold Start: {is_cold_start}")
    print(f"   RAG Results: {len(rag_results)}")
    if matched_rag:
        print(
            f"   Top RAG distance/similarity: "
            f"{matched_rag[0].distance:.4f}/{matched_rag[0].similarity:.4f} "
            f"(threshold={RAG_SIMILARITY_THRESHOLD})"
        )
    print(f"   Facts: {len(facts)}")
    print(f"   Evidence Score: {packet.evidence_score}/100")
    print(f"   Output Level: {guard_result.allowed_output_level.value}")
    print(f"   Reason: {guard_result.reason}\n")
    if ingestion_result is not None:
        print(
            "   Ingestion: "
            f"ingested={ingestion_result.get('ingested', 0)} "
            f"skipped={ingestion_result.get('skipped', 0)}"
        )

    return {
        "evidence_packet": packet.model_dump(mode="json"),
        "cold_start": is_cold_start,
        "ingestion_result": ingestion_result,
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

    # Classify hard vs soft Guard failures.
    # Hard (evidence-level): can't fix by re-running agents → END immediately.
    # Soft (output-level): ungrounded claims / prohibited keywords → retry agents.
    if guard_failed:
        issues = guard_check.get("issues", [])
        hard_failure_keywords = [
            "INSUFFICIENT_EVIDENCE",
            "Symbol mismatch",
            "no evidence packet",
            "evidence packet corrupted",
            "cannot produce analysis",
        ]
        is_hard_failure = any(
            kw.lower() in str(issue).lower()
            for issue in issues
            for kw in hard_failure_keywords
        )

        if is_hard_failure:
            reasoning = (
                f"Guard hard-failure (evidence-level, retry {guard_retry}/{GUARD_MAX_RETRIES}). "
                f"Re-running agents cannot fix this. Ending pipeline."
            )
            print(f"\n🎛️ Orchestrator Decision:")
            print(f"   Executed: {executed}")
            print(f"   Next: []")
            print(f"   Reasoning: {reasoning}\n")
            return {"next": "__end__", "orchestrator_reasoning": reasoning}

        corrections = guard_check.get("corrections", [])
        correction_msg = "\n".join(f"- {c}" for c in corrections) if corrections else "Address the identified issues."
        guard_msg = {"role": "user", "content": f"Guard Agent identified issues:\n{correction_msg}\nPlease fix these and regenerate your analysis."}
        messages.append(guard_msg)
        next_agents = ["strategy_expert"]
        executed = [a for a in executed if a not in ("strategy_expert", "risk_expert", "recommendation_agent", "guard_agent")]
        reasoning = f"Guard soft-failure (output-level, retry {guard_retry}/{GUARD_MAX_RETRIES}). Re-running strategy → risk → recommendation."
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
        ep = state.get("evidence_packet", {})
        allowed_level = ep.get("allowed_output_level", "") if ep else ""
        evidence_score = ep.get("evidence_score", 0) if ep else 0

        if allowed_level in ("insufficient_evidence", "data_summary_only"):
            STAGES: list[list[str]] = []
        elif allowed_level == "limited_analysis":
            STAGES = [
                ["market_data_expert", "fundamental_expert", "news_sentiment_expert"],
                ["strategy_expert"],
                ["risk_expert"],
            ]
        else:
            STAGES = [
                ["market_data_expert", "fundamental_expert", "news_sentiment_expert"],
                ["strategy_expert"],
                ["risk_expert"],
                ["portfolio_agent"],
                ["backtesting_agent"],
            ]

        executed_set = set(executed)
        next_agents = []
        for stage in STAGES:
            missing = [agent for agent in stage if agent not in executed_set]
            if missing:
                next_agents = missing
                break

        if not next_agents:
            if allowed_level in ("insufficient_evidence", "data_summary_only"):
                if "guard_agent" not in executed_set:
                    next_agents = ["guard_agent"]
                    reasoning = (
                        f"Evidence level={allowed_level} (score={evidence_score}). "
                        f"Skipping all analysis. Routing to Guard for rejection."
                    )
                else:
                    reasoning = "Evidence insufficient, guard passed. Pipeline complete."
            elif allowed_level == "limited_analysis":
                if "guard_agent" not in executed_set:
                    next_agents = ["guard_agent"]
                    reasoning = (
                        f"Evidence level={allowed_level} (score={evidence_score}). "
                        f"Analysis done. Routing to Guard (skipping portfolio/backtest/recommendation)."
                    )
                else:
                    reasoning = "Limited analysis + guard complete. Pipeline done."
            else:
                if "recommendation_agent" not in executed_set:
                    next_agents = ["recommendation_agent"]
                    reasoning = "Full analysis done. Routing to recommendation for personalized advice."
                elif "guard_agent" not in executed_set:
                    next_agents = ["guard_agent"]
                    reasoning = "Recommendation complete. Routing to Guard Agent for fact-check verification."
                else:
                    reasoning = "Guard verification passed. Analysis pipeline complete."
        else:
            level_label = allowed_level if allowed_level else "full"
            reasoning = f"Deterministic route ({level_label})."

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

_compiled_app = workflow.compile(checkpointer=checkpointer)


def _extract_symbol_mismatch(guard_check: dict | None) -> bool:
    if not isinstance(guard_check, dict):
        return False
    issues = guard_check.get("issues", [])
    if not isinstance(issues, list):
        return False
    return any("symbol mismatch" in str(issue).lower() for issue in issues)


def _record_request_metrics(
    evidence_packet: dict | None,
    guard_check: dict | None,
    duration_ms: int,
) -> None:
    metrics = get_metrics()
    guard_valid = True
    if isinstance(guard_check, dict) and guard_check:
        guard_valid = bool(guard_check.get("is_valid", False))
    symbol_mismatch = _extract_symbol_mismatch(guard_check)
    metrics.record(
        evidence_packet=evidence_packet,
        guard_valid=guard_valid,
        symbol_mismatch=symbol_mismatch,
        duration_ms=duration_ms,
    )


class InstrumentedWorkflowApp:
    """
    Lightweight wrapper around compiled LangGraph app.
    Records monitoring counters for both invoke and stream paths.
    """

    def __init__(self, inner_app):
        self._inner = inner_app

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def invoke(self, *args, **kwargs):
        t0 = time.time()
        output = self._inner.invoke(*args, **kwargs)
        elapsed_ms = int((time.time() - t0) * 1000)
        ep = output.get("evidence_packet") if isinstance(output, dict) else None
        guard = output.get("guard_check") if isinstance(output, dict) else None
        _record_request_metrics(ep, guard, elapsed_ms)
        return output

    def stream(self, *args, **kwargs):
        t0 = time.time()
        latest_packet = None
        latest_guard = None
        for chunk in self._inner.stream(*args, **kwargs):
            if isinstance(chunk, dict):
                for _node, update in chunk.items():
                    if isinstance(update, dict):
                        if "evidence_packet" in update:
                            latest_packet = update.get("evidence_packet")
                        if "guard_check" in update:
                            latest_guard = update.get("guard_check")
            yield chunk
        elapsed_ms = int((time.time() - t0) * 1000)
        _record_request_metrics(latest_packet, latest_guard, elapsed_ms)


app = InstrumentedWorkflowApp(_compiled_app)

__all__ = ["app"]