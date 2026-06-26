"""
逐个测试各 Agent 是否真正使用了 Document Evidence。

用法:
    cd alphapilot
    python test/test_rag_document_usage.py

每个 Agent 的输出会打印到控制台，末尾有 ✅/⚠️/❌ 标记，
方便肉眼判断是否引用了文档 RAG 内容。
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from schemas.evidence_packet import (
    Coverage,
    EvidencePacket,
    Fact,
    DocumentChunk,
    compute_evidence_score,
    determine_output_level,
    detect_conflicts,
    render_packet_for_agent,
)

# ── 构造一份假的 Document Evidence，内容带有唯一标记便于识别 ──

_MARKER = "RAG_DOC_TEST_MARKER_v9x3k"  # 唯一标识，搜索输出中是否含此内容

_DOC_EVIDENCE = [
    DocumentChunk(
        chunk_id="chunk_001",
        content=(
            f"[{_MARKER}] Management stated in the 2024 Annual Report: "
            "The company is investing heavily in next-generation autonomous driving technology. "
            "Revenue from the energy storage segment grew 67% year-over-year, "
            "becoming a significant growth driver. "
            "However, the Risk Factors section notes: 'Supply chain disruptions "
            "and lithium price volatility could materially impact gross margins in FY2025.'"
        ),
        source="2024_annual_report",
        doc_id="tsla_2024_annual_report",
        doc_type="annual_report",
        section="Management Discussion & Risk Factors",
        page="24-27",
        publish_date="2025-02-15",
        report_period="FY2024",
        symbol="TSLA",
    ),
    DocumentChunk(
        chunk_id="chunk_002",
        content=(
            f"[{_MARKER}] In the Q4 earnings call, the CEO noted: "
            "'We expect Model Y to become the best-selling vehicle globally in 2025. "
            "Our new manufacturing process reduces production cost by 30% per unit.' "
            "The CFO added: 'We anticipate capex of $11 billion in 2025, "
            "primarily for the new Gigafactory and AI training infrastructure.'"
        ),
        source="earnings_call_transcript",
        doc_id="tsla_q4_2024_earnings_call",
        doc_type="earnings_call",
        section="Q&A Session",
        page="8",
        publish_date="2025-01-24",
        report_period="Q4 2024",
        symbol="TSLA",
    ),
]

# ── 构造一个含有足够 facts 的 EvidencePacket（确保能通过 output level 检查） ──

def _build_packet() -> EvidencePacket:
    packet = EvidencePacket(
        symbol="TSLA",
        request_type="comprehensive_analysis",
        is_cold_start=False,
        coverage=Coverage(
            rag_context="available",
            market_data="available",
            fundamental_data="available",
            news_data="available",
            filings="missing",
            document_evidence="available",
        ),
        facts=[
            # 市场数据
            Fact(field="current_price", value=385.01, unit="USD", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.95, confidence_tier="machine"),
            Fact(field="price_change_pct", value=2.64, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.95, confidence_tier="machine"),
            Fact(field="rsi_14", value=47.8, unit="index", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.90, confidence_tier="machine"),
            Fact(field="macd", value=-7.48, unit="index", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.90, confidence_tier="machine"),
            Fact(field="volatility_20d_annualized", value=44.79, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.90, confidence_tier="machine"),
            # 基本面数据
            Fact(field="revenue_growth_yoy", value=15.8, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.90, confidence_tier="machine"),
            Fact(field="eps_growth_yoy", value=8.3, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.90, confidence_tier="machine"),
            Fact(field="pe_ratio", value=353.25, unit="ratio", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.90, confidence_tier="machine"),
            Fact(field="market_cap", value=1.446e12, unit="USD", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.90, confidence_tier="machine"),
            Fact(field="gross_margin", value=19.06, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.85, confidence_tier="machine"),
            Fact(field="net_margin", value=3.95, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-26", confidence=0.85, confidence_tier="machine"),
            # 新闻数据
            Fact(field="news_headline", value="Robotaxi regulation easing expected to benefit Tesla, Amazon, Google", unit="text", period="latest", source="Yahoo", as_of_date="2026-06-26", confidence=0.70, confidence_tier="llm_extracted"),
        ],
        document_evidence=_DOC_EVIDENCE,
    )
    packet = detect_conflicts(packet)
    packet = compute_evidence_score(packet)
    guard_result = determine_output_level(packet)
    packet.allowed_output_level = guard_result.allowed_output_level
    return packet


def _get_output(result: dict) -> str:
    """兼容各 Agent 不同返回格式，提取最终输出文本。"""
    last_msg = result.get("messages", [None])[-1]
    if last_msg is None:
        return ""
    if isinstance(last_msg, str):
        return last_msg
    if isinstance(last_msg, dict):
        return str(last_msg.get("content", ""))
    return str(getattr(last_msg, "content", ""))


def _render_and_print(agent_name: str, output: str) -> str:
    """打印 Agent 输出并返回简短判定。"""
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  {agent_name}")
    print(f"{sep}")
    print(output[:3000])
    if len(output) > 3000:
        print(f"\n... (truncated, total {len(output)} chars)")
    print(f"{sep}\n")

    # 判定：检查是否引用了文档证据（搜索文档来源名称和文档特有内容）
    doc_keywords = [
        "tsla_2024_annual_report",
        "tsla_q4_2024_earnings_call",
        "2024年年报",
        "2024年年度报告",
        "Q4财报电话",
        "Q4 earnings call",
        "Document Evidence",
        "文档证据",
        "earnings_call_transcript",
        "annual_report",
    ]
    has_doc_ref = any(kw.lower() in output.lower() for kw in doc_keywords)
    if has_doc_ref:
        return "✅ 使用了 RAG 文档证据"
    else:
        return "⚠️  未检测到 RAG 文档引用"


# ── 测试 1: Fundamental Agent ──

def test_fundamental_agent():
    from agents.fundamental_agent import fundamental_agent

    packet = _build_packet()
    rendered = render_packet_for_agent(packet, language="")

    state = {
        "messages": [
            {"role": "system", "content": rendered},
            {"role": "user", "content": "请对 TSLA 进行基本面分析"},
        ],
        "evidence_packet": packet.model_dump(mode="json"),
    }

    result = fundamental_agent(state)
    output = _get_output(result)
    return _render_and_print("Fundamental Agent", output)


# ── 测试 2: News Agent ──

def test_news_agent():
    from agents.news_agent import news_agent

    packet = _build_packet()
    rendered = render_packet_for_agent(packet, language="")

    state = {
        "messages": [
            {"role": "system", "content": rendered},
            {"role": "user", "content": "请对 TSLA 进行新闻情绪分析"},
        ],
        "evidence_packet": packet.model_dump(mode="json"),
    }

    result = news_agent(state)
    output = _get_output(result)
    return _render_and_print("News Agent", output)


# ── 测试 3: Bull Researcher ──

def test_bull_researcher():
    from agents.bull_researcher import bull_researcher

    packet = _build_packet()
    rendered = render_packet_for_agent(packet, language="")

    state = {
        "messages": [
            {"role": "system", "content": rendered},
            {"role": "user", "content": "请给出 TSLA 的看多论据"},
        ],
        "evidence_packet": packet.model_dump(mode="json"),
        "debate_rounds": 0,
    }

    result = bull_researcher(state)
    output = _get_output(result)
    return _render_and_print("Bull Researcher", output)


# ── 测试 4: Bear Researcher ──

def test_bear_researcher():
    from agents.bear_researcher import bear_researcher

    packet = _build_packet()
    rendered = render_packet_for_agent(packet, language="")

    state = {
        "messages": [
            {"role": "system", "content": rendered},
            {"role": "user", "content": "请给出 TSLA 的看空论据"},
        ],
        "evidence_packet": packet.model_dump(mode="json"),
        "debate_rounds": 0,
    }

    result = bear_researcher(state)
    output = _get_output(result)
    return _render_and_print("Bear Researcher", output)


# ── 测试 5: Strategy Agent ──

def test_strategy_agent():
    from agents.strategy_agent import strategy_agent

    packet = _build_packet()
    rendered = render_packet_for_agent(packet, language="")

    state = {
        "messages": [
            {"role": "system", "content": rendered},
            {"role": "user", "content": "请基于证据包给出 TSLA 的综合策略评估"},
            # 模拟上游 Agent 输出（strategy 需要这些来做加权判断）
            {"role": "assistant", "content": "Market: RSI 47.8 neutral, MACD bearish", "name": "market_data_expert"},
            {"role": "assistant", "content": "Fundamental: PE 353x, revenue growth 15.8%, net margin 3.95%", "name": "fundamental_expert"},
            {"role": "assistant", "content": "News: Robotaxi regulation easing, sentiment slightly positive", "name": "news_sentiment_expert"},
        ],
        "evidence_packet": packet.model_dump(mode="json"),
    }

    result = strategy_agent(state)
    output = _get_output(result)
    return _render_and_print("Strategy Agent", output)


# ── 测试 6: Risk Agent ──

def test_risk_agent():
    from agents.risk_agent import risk_agent

    packet = _build_packet()
    rendered = render_packet_for_agent(packet, language="")

    state = {
        "messages": [
            {"role": "system", "content": rendered},
            {"role": "user", "content": "请对 TSLA 进行风险评估"},
        ],
        "evidence_packet": packet.model_dump(mode="json"),
    }

    result = risk_agent(state)
    output = _get_output(result)
    return _render_and_print("Risk Agent", output)


# ── 测试 7: Recommendation Agent ──

def test_recommendation_agent():
    from agents.recommendation_agent import recommendation_agent

    packet = _build_packet()
    # 推荐 Agent 不使用 render_packet_for_agent，而是自己构建 compact_context
    # 但 compact_context 中的 _render_document_evidence 需要 ep 是 dict 形式

    state = {
        "messages": [
            {"role": "user", "content": "请对 TSLA 进行综合分析"},
            # 模拟上游 Agent 输出
            {"role": "assistant", "content": "Market: RSI 47.8 neutral, MACD bearish, price 385.01", "name": "market_data_expert"},
            {"role": "assistant", "content": "Fundamental: PE 353x, revenue growth 15.8%, net margin 3.95%, ROE 4.9%", "name": "fundamental_expert"},
            {"role": "assistant", "content": "News: Robotaxi regulation easing, sentiment slightly positive (score 0.55)", "name": "news_sentiment_expert"},
            {"role": "assistant", "content": "Bull: Strong cash position $447B, forward PE improving", "name": "bull_researcher"},
            {"role": "assistant", "content": "Bear: Overvalued, low profitability, high volatility", "name": "bear_researcher"},
            {"role": "assistant", "content": "Strategy: SELL, confidence 70/100, bearish bias", "name": "strategy_expert"},
            {"role": "assistant", "content": "Risk: Overall 76/100, high volatility, position <4%", "name": "risk_expert"},
        ],
        "evidence_packet": packet.model_dump(mode="json"),
        "user_profile": {"risk_preference": "medium", "horizon": "long"},
    }

    result = recommendation_agent(state)
    output = _get_output(result)
    return _render_and_print("Recommendation Agent", output)


# ── 全部执行 ──

if __name__ == "__main__":
    results = []

    print("\n🧪 逐个测试 Agent 是否使用 RAG Document Evidence")
    print(f"   唯一标记: '{_MARKER}' (搜索 Agent 输出中是否包含此字符串)")

    results.append(("Fundamental Agent", test_fundamental_agent()))
    results.append(("News Agent", test_news_agent()))
    results.append(("Bull Researcher", test_bull_researcher()))
    results.append(("Bear Researcher", test_bear_researcher()))
    results.append(("Strategy Agent", test_strategy_agent()))
    results.append(("Risk Agent", test_risk_agent()))
    results.append(("Recommendation Agent", test_recommendation_agent()))

    print("\n" + "=" * 70)
    print("  汇总")
    print("=" * 70)
    for name, status in results:
        print(f"  {status}  |  {name}")
    print("=" * 70)
