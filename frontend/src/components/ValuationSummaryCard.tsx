import { useMemo, type ReactNode } from "react";
import { Target, ShieldCheck, TrendingUp, AlertTriangle, Info, CheckCircle2, XCircle, Search, Database, FileWarning } from "lucide-react";
import type { EvidencePacketData, GuardCheck, TargetPriceData, RiskLevelData } from "../services/sse";

type ValuationSummaryCardProps = {
  evidence: EvidencePacketData | null;
  guard: GuardCheck | null;
  recommendation?: string;
  targetPrice?: TargetPriceData | null;
  riskLevel?: RiskLevelData | null;
};

type RiskLevel = "low" | "medium" | "high" | "unknown";

function getFactVal(facts: EvidencePacketData["facts"], field: string): number | undefined {
  const f = facts?.find((x) => x.field === field);
  if (!f) return undefined;
  const n = typeof f.value === "string" ? parseFloat(f.value) : f.value;
  return isNaN(n) ? undefined : n;
}

function deriveRiskLevel(riskLevel: RiskLevelData | null | undefined, evidence: EvidencePacketData | null, guard: GuardCheck | null): RiskLevel {
  // 优先使用 risk_agent 的结构化风险评分
  if (riskLevel?.overall_risk_score !== undefined) {
    const s = riskLevel.overall_risk_score;
    if (s <= 30) return "low";
    if (s <= 60) return "medium";
    return "high";
  }
  const score = guard?.confidence_score ?? evidence?.evidence_score ?? 0;
  if (score >= 80) return "low";
  if (score >= 60) return "medium";
  if (score > 0) return "high";
  return "unknown";
}

const RISK_CONFIG: Record<RiskLevel, { label: string; color: string; bg: string; icon: ReactNode }> = {
  low:    { label: "低风险",   color: "#22c55e", bg: "rgba(34,197,94,0.1)",   icon: <ShieldCheck size={15} /> },
  medium: { label: "中风险",   color: "#f59e0b", bg: "rgba(245,158,11,0.1)",  icon: <AlertTriangle size={15} /> },
  high:   { label: "高风险",   color: "#ef4444", bg: "rgba(239,68,68,0.1)",   icon: <AlertTriangle size={15} /> },
  unknown:{ label: "未知",     color: "#6b7280", bg: "rgba(107,114,128,0.1)", icon: <Info size={15} /> },
};

export default function ValuationSummaryCard({ evidence, guard, recommendation, targetPrice, riskLevel }: ValuationSummaryCardProps) {
  const price = getFactVal(evidence?.facts ?? [], "current_price");
  const changePct = getFactVal(evidence?.facts ?? [], "price_change_pct");
  const volatility = getFactVal(evidence?.facts ?? [], "volatility_20d_annualized");
  const evidenceScore = evidence?.evidence_score ?? 0;
  const guardScore = guard?.confidence_score ?? 0;
  const risk = deriveRiskLevel(riskLevel, evidence, guard);
  const riskCfg = RISK_CONFIG[risk];
  const valuationLow = targetPrice?.valuation_low ?? targetPrice?.target_price_low ?? null;
  const valuationMid = targetPrice?.valuation_mid ?? targetPrice?.target_price_mid ?? null;
  const valuationHigh = targetPrice?.valuation_high ?? targetPrice?.target_price_high ?? null;

  // 结构化估值情景是否可用。旧字段名保持兼容，展示语义不承诺正式目标价。
  const hasStructuredTarget = targetPrice && (
    valuationLow != null ||
    valuationMid != null ||
    valuationHigh != null
  );

  const consensusText = useMemo(() => {
    if (targetPrice?.consensus_summary) return targetPrice.consensus_summary;
    if (guard?.final_reasoning) return guard.final_reasoning;
    if (recommendation) {
      const first = recommendation.split(/[。.!！?\n]/).filter(Boolean)[0];
      return first ? first.trim() : recommendation.slice(0, 120);
    }
    return undefined;
  }, [targetPrice, guard, recommendation]);

  const isReady = price !== undefined || evidenceScore > 0 || guardScore > 0;

  return (
    <div className="valuation-summary">
      {/* Header row */}
      <div className="vs-header">
        <div className="vs-header-left">
          <Target size={18} />
          <span>估值与结论摘要</span>
        </div>
        {evidence?.evidence_score !== undefined && (
          <div className="vs-header-right">
            <span className="vs-evidence-score">
              证据评分 {evidenceScore}/100
            </span>
          </div>
        )}
      </div>

      {!isReady ? (
        <div className="vs-empty">
          <Info size={20} />
          <span>分析结果尚未就绪</span>
        </div>
      ) : (
        <div className="vs-body">
          {/* Price + change + risk */}
          <div className="vs-price-row">
            <div className="vs-price-block">
              <span className="vs-price-label">当前价格</span>
              <span className="vs-price-value">
                {price !== undefined ? price.toFixed(2) : "N/A"}
              </span>
              {changePct !== undefined && (
                <span
                  className="vs-price-change"
                  style={{ color: changePct >= 0 ? "#22c55e" : "#ef4444" }}
                >
                  {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
                </span>
              )}
            </div>

            <div className="vs-risk-badge" style={{ color: riskCfg.color, background: riskCfg.bg }}>
              {riskCfg.icon}
              <span>{riskCfg.label}</span>
            </div>
          </div>

          {/* Valuation scenario section */}
          <div className="vs-target-section">
            <div className="vs-target-header">
              <TrendingUp size={14} />
              <span>估值情景区间</span>
              {!hasStructuredTarget && (
                <span className="vs-target-placeholder-tag">暂未结构化</span>
              )}
            </div>
            <div className="vs-target-grid">
              <div className="vs-target-item">
                <span className="vs-target-label">低</span>
                <span className={hasStructuredTarget ? "vs-target-value" : "vs-target-value vs-target-na"}>
                  {valuationLow != null
                    ? valuationLow.toFixed(2)
                    : "---"}
                </span>
                {targetPrice?.downside_pct != null && (
                  <span className="vs-target-pct down">
                    {(targetPrice.downside_pct >= 0 ? "-" : "") + Math.abs(targetPrice.downside_pct).toFixed(1)}%
                  </span>
                )}
              </div>
              <div className="vs-target-item vs-target-mid">
                <span className="vs-target-label">中</span>
                <span className={hasStructuredTarget ? "vs-target-value" : "vs-target-value vs-target-na"}>
                  {valuationMid != null
                    ? valuationMid.toFixed(2)
                    : "---"}
                </span>
                {targetPrice?.upside_pct != null && (
                  <span
                    className="vs-target-pct"
                    style={{ color: targetPrice.upside_pct >= 0 ? "#22c55e" : "#ef4444" }}
                  >
                    {(targetPrice.upside_pct >= 0 ? "+" : "") + targetPrice.upside_pct.toFixed(1)}%
                  </span>
                )}
              </div>
              <div className="vs-target-item">
                <span className="vs-target-label">高</span>
                <span className={hasStructuredTarget ? "vs-target-value" : "vs-target-value vs-target-na"}>
                  {valuationHigh != null
                    ? valuationHigh.toFixed(2)
                    : "---"}
                </span>
              </div>
            </div>
            {!hasStructuredTarget && (
              <p className="vs-target-hint">
                估值情景需由 Recommendation Agent 输出结构化 metadata 后展示，当前版本不会从报告正文自动解析。
              </p>
            )}
          </div>

          {/* Guard confidence + consensus */}
          <div className="vs-bottom">
            <div className="vs-guard-row">
              <div className="vs-guard-stat">
                <span className="vs-guard-label">证据可信度</span>
                <div className="vs-guard-bar-wrap">
                  <div
                    className="vs-guard-bar"
                    style={{
                      width: `${Math.min(guardScore, 100)}%`,
                      background:
                        guardScore >= 80
                          ? "linear-gradient(90deg, #22c55e, #4ade80)"
                          : guardScore >= 60
                          ? "linear-gradient(90deg, #f59e0b, #fbbf24)"
                          : "linear-gradient(90deg, #ef4444, #f87171)",
                    }}
                  />
                </div>
                <span
                  className="vs-guard-score"
                  style={{
                    color:
                      guardScore >= 80 ? "#4ade80" : guardScore >= 60 ? "#fbbf24" : "#f87171",
                  }}
                >
                  {guardScore}/100
                </span>
              </div>

              <div className="vs-guard-stat">
                <span className="vs-guard-label">
                  {riskLevel?.overall_risk_score !== undefined ? "投资风险评分" : "年化波动率"}
                </span>
                {riskLevel?.overall_risk_score !== undefined ? (
                  <span
                    className="vs-guard-value"
                    style={{
                      color:
                        riskLevel.overall_risk_score <= 30 ? "#4ade80" :
                        riskLevel.overall_risk_score <= 60 ? "#fbbf24" : "#f87171",
                    }}
                  >
                    {riskLevel.overall_risk_score}/100
                  </span>
                ) : volatility !== undefined ? (
                  <span className="vs-guard-value">{volatility.toFixed(1)}%</span>
                ) : null}
              </div>
            </div>
            {riskLevel?.overall_risk_score !== undefined && guardScore > 0 && (
              <p className="vs-score-note">
                证据可信度衡量数据与校验质量；投资风险评分衡量标的自身风险，二者不是同一维度。
              </p>
            )}

            {consensusText && (
              <div className="vs-consensus">
                <span className="vs-consensus-label">综合观点</span>
                <p className="vs-consensus-text">{consensusText}</p>
              </div>
            )}

            {riskLevel?.risk_reasoning && (
              <div className="vs-consensus">
                <span className="vs-consensus-label">风险分析</span>
                <p className="vs-consensus-text">{riskLevel.risk_reasoning}</p>
              </div>
            )}

            {/* Guard 检查项明细 */}
            {guard && (
              <GuardCheckItems guard={guard} evidenceScore={evidenceScore} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Guard 检查项明细面板
   ══════════════════════════════════════════════════════════════════════ */

type GuardCheckCategory = {
  key: string;
  label: string;
  icon: ReactNode;
  items: string[];
  passed: boolean;
};

function GuardCheckItems({ guard, evidenceScore: _evidenceScore }: { guard: GuardCheck; evidenceScore: number }) {
  const checks = guard.checks;
  const hasStructured = checks && (
    checks.data_coverage !== undefined ||
    checks.symbol_match !== undefined ||
    checks.unsupported_claim !== undefined
  );

  // 有结构化 checks → 使用后端结构化数据
  if (hasStructured) {
    const checkList = [
      { key: "data_coverage", label: "数据覆盖", icon: <Database size={13} />, ...checks.data_coverage },
      { key: "symbol_match", label: "标的匹配", icon: <Search size={13} />, ...checks.symbol_match },
      { key: "unsupported_claim", label: "无依据声明", icon: <FileWarning size={13} />, ...checks.unsupported_claim },
    ];
    const allPassed = checkList.every((c) => c.passed);

    return (
      <div className="vs-guard-checks">
        <div className="vs-guard-checks-header">
          <ShieldCheck size={15} style={{ color: allPassed ? "#22c55e" : "#f59e0b" }} />
          <span>Guard 检查项</span>
          <span className={`vs-guard-checks-badge ${allPassed ? "pass" : "fail"}`}>
            {allPassed ? "全部通过" : `${checkList.filter((c) => !c.passed).length} 项未通过`}
          </span>
        </div>

        {guard.final_reasoning && (
          <p className="vs-guard-reasoning">{guard.final_reasoning}</p>
        )}

        <div className="vs-guard-checks-list">
          {checkList.map((cat) => (
            <div key={cat.key} className={`vs-guard-check-cat ${cat.passed ? "pass" : "fail"}`}>
              <div className="vs-guard-check-cat-hd">
                {cat.passed ? <CheckCircle2 size={13} color="#22c55e" /> : <XCircle size={13} color="#ef4444" />}
                <span className="vs-guard-check-cat-icon">{cat.icon}</span>
                <span className="vs-guard-check-cat-label">{cat.label}</span>
                <span className="vs-guard-check-cat-reason">
                  {cat.passed ? "通过" : "未通过"}
                  {cat.detail && `\u2009\u2014\u2009${cat.detail.slice(0, 80)}`}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Fallback: 无结构化 checks → 从 issues 文本关键词分类
  const issues = guard.issues ?? [];
  const corrections = guard.corrections ?? [];
  const allIssues = [...new Set([...issues, ...corrections])];
  const cats: Record<string, GuardCheckCategory> = {
    data_coverage: { key: "data_coverage", label: "数据覆盖", icon: <Database size={13} />, items: [], passed: true },
    symbol_match: { key: "symbol_match", label: "标的匹配", icon: <Search size={13} />, items: [], passed: true },
    unsupported: { key: "unsupported", label: "无依据声明", icon: <FileWarning size={13} />, items: [], passed: true },
    other: { key: "other", label: "其他检查", icon: <Info size={13} />, items: [], passed: true },
  };
  for (const iss of allIssues) {
    const lower = iss.toLowerCase();
    if (lower.includes("symbol mismatch") || lower.includes("symbol_mismatch")) {
      cats.symbol_match.items.push(iss); cats.symbol_match.passed = false;
    } else if (lower.includes("insufficient_evidence") || lower.includes("insufficient evidence") || lower.includes("data_summary") || lower.includes("coverage")) {
      cats.data_coverage.items.push(iss); cats.data_coverage.passed = false;
    } else if (lower.includes("unverified_claim") || lower.includes("ungrounded") || lower.includes("unsupported")) {
      cats.unsupported.items.push(iss); cats.unsupported.passed = false;
    } else {
      cats.other.items.push(iss); cats.other.passed = false;
    }
  }
  const categories: GuardCheckCategory[] = Object.values(cats).filter((c) => c.items.length > 0);

  const allPassed = categories.length === 0 || categories.every((c) => c.passed);

  return (
    <div className="vs-guard-checks">
      <div className="vs-guard-checks-header">
        <ShieldCheck size={15} style={{ color: allPassed ? "#22c55e" : "#f59e0b" }} />
        <span>Guard 检查项</span>
        <span className={`vs-guard-checks-badge ${allPassed ? "pass" : "fail"}`}>
          {allPassed ? "全部通过" : `${categories.filter((c) => !c.passed).length} 项未通过`}
        </span>
      </div>
      {guard.final_reasoning && (
        <p className="vs-guard-reasoning">{guard.final_reasoning}</p>
      )}
      <div className="vs-guard-checks-list">
        {categories.map((cat) => (
          <div key={cat.key} className={`vs-guard-check-cat ${cat.passed ? "pass" : "fail"}`}>
            <div className="vs-guard-check-cat-hd">
              {cat.passed ? <CheckCircle2 size={13} color="#22c55e" /> : <XCircle size={13} color="#ef4444" />}
              <span className="vs-guard-check-cat-icon">{cat.icon}</span>
              <span className="vs-guard-check-cat-label">{cat.label}</span>
              <span className="vs-guard-check-cat-count">{cat.items.length}</span>
            </div>
            <ul className="vs-guard-check-items">
              {cat.items.map((item, j) => (<li key={j}>{item}</li>))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
