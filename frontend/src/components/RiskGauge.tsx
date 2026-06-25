import { ShieldAlert, TrendingUp, TrendingDown, Gauge, AlertTriangle } from "lucide-react";
import type { EvidencePacketData, GuardCheck, RiskLevelData } from "../services/sse";

type RiskGaugeProps = {
  evidence: EvidencePacketData | null;
  guard: GuardCheck | null;
  riskLevel: RiskLevelData | null;
};

type RiskLevel = "low" | "medium" | "high" | "unknown";

function getFactVal(facts: EvidencePacketData["facts"], field: string): number | undefined {
  const f = facts?.find((x) => x.field === field);
  if (!f) return undefined;
  const n = typeof f.value === "string" ? parseFloat(f.value) : f.value;
  return isNaN(n) ? undefined : n;
}

function deriveRisk(riskLevel: RiskLevelData | null, evidence: EvidencePacketData | null): RiskLevel {
  if (riskLevel?.overall_risk_score !== undefined) {
    const s = riskLevel.overall_risk_score;
    if (s <= 30) return "low";
    if (s <= 60) return "medium";
    return "high";
  }
  const score = evidence?.evidence_score ?? 0;
  if (score >= 80) return "low";
  if (score >= 60) return "medium";
  if (score > 0) return "high";
  return "unknown";
}

const RISK_META: Record<RiskLevel, { label: string; color: string; gradient: [string, string] }> = {
  low:     { label: "低风险",   color: "#22c55e", gradient: ["#22c55e", "#4ade80"] },
  medium:  { label: "中等风险", color: "#f59e0b", gradient: ["#f59e0b", "#fbbf24"] },
  high:    { label: "高风险",   color: "#ef4444", gradient: ["#ef4444", "#f87171"] },
  unknown: { label: "未知",     color: "#6b7280", gradient: ["#6b7280", "#9ca3af"] },
};

/* ── SVG 半圆仪表盘 ── */
const GAUGE_R = 70;
const GAUGE_CX = 110;
const GAUGE_CY = 90;
const ARC_START = -210; // degrees
const ARC_END = 30;     // degrees
const ARC_SPAN = ARC_END - ARC_START; // 240°

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polar(cx, cy, r, startDeg);
  const e = polar(cx, cy, r, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}

function RiskArc({ score }: { score: number }) {
  const bg = arcPath(GAUGE_CX, GAUGE_CY, GAUGE_R, ARC_START, ARC_END);
  // colored segments: low (green) 0-30, medium (yellow) 30-60, high (red) 60-100
  const seg30 = ARC_START + ARC_SPAN * 0.3;
  const seg60 = ARC_START + ARC_SPAN * 0.6;
  const segEnd = ARC_END;

  return (
    <svg viewBox="0 0 220 130" width="100%" height="130" className="risk-gauge-svg">
      {/* background track */}
      <path d={bg} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="14" strokeLinecap="round" />

      {/* colored segments */}
      <path d={arcPath(GAUGE_CX, GAUGE_CY, GAUGE_R, ARC_START, seg30)} fill="none" stroke="#22c55e" strokeWidth="14" strokeLinecap="butt" opacity="0.6" />
      <path d={arcPath(GAUGE_CX, GAUGE_CY, GAUGE_R, seg30, seg60)} fill="none" stroke="#f59e0b" strokeWidth="14" strokeLinecap="butt" opacity="0.6" />
      <path d={arcPath(GAUGE_CX, GAUGE_CY, GAUGE_R, seg60, segEnd)} fill="none" stroke="#ef4444" strokeWidth="14" strokeLinecap="butt" opacity="0.6" />

      {/* active indicator arc */}
      {score > 0 && (
        <>
          <path
            d={arcPath(GAUGE_CX, GAUGE_CY, GAUGE_R, ARC_START, ARC_START + ARC_SPAN * (score / 100))}
            fill="none"
            stroke={
              score <= 30 ? "#22c55e" : score <= 60 ? "#f59e0b" : "#ef4444"
            }
            strokeWidth="14"
            strokeLinecap="round"
            style={{ transition: "all 0.6s ease" }}
          />
          {/* needle dot */}
          {(() => {
            const deg = ARC_START + ARC_SPAN * (score / 100);
            const p = polar(GAUGE_CX, GAUGE_CY, GAUGE_R - 0, deg);
            return <circle cx={p.x} cy={p.y} r="5" fill="#fff" />;
          })()}
        </>
      )}

      {/* center text */}
      <text x={GAUGE_CX} y={GAUGE_CY - 14} textAnchor="middle" fontSize="26" fontWeight="800" fill="rgba(255,255,255,0.92)" fontFamily="monospace">
        {score > 0 ? score : "--"}
      </text>
      <text x={GAUGE_CX} y={GAUGE_CY + 6} textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.35)">
        /100
      </text>

      {/* min/max labels */}
      <text x={polar(GAUGE_CX, GAUGE_CY, GAUGE_R + 16, ARC_START).x} y={polar(GAUGE_CX, GAUGE_CY, GAUGE_R + 16, ARC_START).y + 4} textAnchor="middle" fontSize="8" fill="rgba(255,255,255,0.25)">0</text>
      <text x={polar(GAUGE_CX, GAUGE_CY, GAUGE_R + 16, ARC_END).x} y={polar(GAUGE_CX, GAUGE_CY, GAUGE_R + 16, ARC_END).y + 4} textAnchor="middle" fontSize="8" fill="rgba(255,255,255,0.25)">100</text>
    </svg>
  );
}

export default function RiskGauge({ evidence, guard, riskLevel }: RiskGaugeProps) {
  const facts = evidence?.facts ?? [];
  const volatility = getFactVal(facts, "volatility_20d_annualized");
  const maxDrawdown = getFactVal(facts, "max_drawdown");
  const sharpe = getFactVal(facts, "sharpe_ratio_annual");
  const sortino = getFactVal(facts, "sortino_ratio_annual");
  const var95 = getFactVal(facts, "var_95_daily");

  const riskScore = riskLevel?.overall_risk_score ?? 0;
  const riskRating = deriveRisk(riskLevel, evidence);
  const meta = RISK_META[riskRating];

  const guardWarnings = guard?.risk_warnings ?? [];

  const hasData = riskScore > 0 || volatility !== undefined || maxDrawdown !== undefined || riskLevel;

  return (
    <div className="risk-gauge">
      <div className="risk-gauge-header">
        <ShieldAlert size={18} color={meta.color} />
        <span>风险评估</span>
      </div>

      {!hasData ? (
        <div className="risk-gauge-empty">
          <Gauge size={24} />
          <span>风险数据尚未就绪</span>
        </div>
      ) : (
        <div className="risk-gauge-body">
          {/* 大仪表盘 */}
          <div className="risk-gauge-chart">
            <RiskArc score={riskScore} />
            <div className="risk-gauge-level" style={{ color: meta.color }}>
              {meta.label}
            </div>
          </div>

          {/* 关键风险指标 */}
          <div className="risk-metrics">
            {volatility !== undefined && (
              <div className="risk-metric-item">
                <TrendingUp size={13} />
                <span className="risk-metric-label">年化波动率</span>
                <span className="risk-metric-value">{volatility.toFixed(1)}%</span>
              </div>
            )}
            {maxDrawdown !== undefined && (
              <div className="risk-metric-item">
                <TrendingDown size={13} color="#ef4444" />
                <span className="risk-metric-label">最大回撤</span>
                <span className="risk-metric-value" style={{ color: "#f87171" }}>{maxDrawdown.toFixed(1)}%</span>
              </div>
            )}
            {sharpe !== undefined && (
              <div className="risk-metric-item">
                <span className="risk-metric-label">夏普比率</span>
                <span className="risk-metric-value" style={{ color: sharpe >= 1 ? "#4ade80" : sharpe >= 0 ? "#fbbf24" : "#f87171" }}>
                  {sharpe.toFixed(2)}
                </span>
              </div>
            )}
            {sortino !== undefined && (
              <div className="risk-metric-item">
                <span className="risk-metric-label">索提诺比率</span>
                <span className="risk-metric-value">{sortino.toFixed(2)}</span>
              </div>
            )}
            {var95 !== undefined && (
              <div className="risk-metric-item">
                <span className="risk-metric-label">VaR(95%)</span>
                <span className="risk-metric-value" style={{ color: "#f87171" }}>{var95.toFixed(2)}%</span>
              </div>
            )}
          </div>

          {/* Risk Agent 建议 */}
          {riskLevel && (
            <div className="risk-agent-advice">
              {riskLevel.key_risks && riskLevel.key_risks.length > 0 && (
                <div className="risk-key-risks">
                  <div className="risk-key-risks-hd">
                    <AlertTriangle size={13} color="#f59e0b" />
                    <span>关键风险点</span>
                  </div>
                  <ul className="risk-key-risks-list">
                    {riskLevel.key_risks.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {riskLevel.stop_loss_suggestion && (
                <div className="risk-advice-item">
                  <span className="risk-advice-label">建议止损</span>
                  <span className="risk-advice-value">
                    {typeof riskLevel.stop_loss_suggestion === "number"
                      ? riskLevel.stop_loss_suggestion.toFixed(2)
                      : riskLevel.stop_loss_suggestion}
                  </span>
                </div>
              )}
              {riskLevel.position_suggestion && (
                <div className="risk-advice-item">
                  <span className="risk-advice-label">建议仓位</span>
                  <span className="risk-advice-value">{riskLevel.position_suggestion}</span>
                </div>
              )}
              {riskLevel.volatility_risk && (
                <div className="risk-advice-item">
                  <span className="risk-advice-label">波动风险</span>
                  <span className="risk-advice-value">{riskLevel.volatility_risk}</span>
                </div>
              )}
              {riskLevel.macro_risk && (
                <div className="risk-advice-item">
                  <span className="risk-advice-label">宏观风险</span>
                  <span className="risk-advice-value">{riskLevel.macro_risk}</span>
                </div>
              )}
            </div>
          )}

          {/* Risk Agent 推理 */}
          {riskLevel?.risk_reasoning && (
            <div className="risk-reasoning">
              <span className="risk-reasoning-label">风险分析</span>
              <p className="risk-reasoning-text">{riskLevel.risk_reasoning}</p>
            </div>
          )}

          {/* Guard 风险提示 */}
          {guardWarnings.length > 0 && (
            <div className="risk-guard-warnings">
              <div className="risk-guard-warn-hd">
                <AlertTriangle size={13} color="#f59e0b" />
                <span>Guard 风险提示</span>
              </div>
              <ul className="risk-guard-warn-list">
                {guardWarnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
