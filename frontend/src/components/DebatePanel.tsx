import { useMemo } from "react";
import { TrendingUp, TrendingDown, Gavel, Database, Target, Zap } from "lucide-react";
import type { EvidencePacketData, GuardCheck, DebateStructuredData, DebateClaim } from "../services/sse";

/** Agent 状态（与 AnalyzePage 中 AgentStatus 对齐） */
type AgentInfo = {
  agent: string;
  label: string;
  icon: string;
  status: string;
  content: string;
  startedAt?: number;
  finishedAt?: number;
};

/* ══════════════════════════════════════════════════════════════════════
   DebatePanel — Bull vs Bear 双栏 + 策略裁决摘要
   ══════════════════════════════════════════════════════════════════════ */

type DebatePanelProps = {
  agents: AgentInfo[];
  evidence: EvidencePacketData | null;
  guard: GuardCheck | null;
  recommendation: string;
};

function getContent(agents: AgentInfo[], id: string): string {
  return agents.find((a) => a.agent === id)?.content ?? "";
}

/** 尝试从 agent 内容解析 JSON，返回结构化数据或 null */
function tryParseDebateData(content: string): DebateStructuredData | null {
  const m = content.match(/\{[\s\S]*\}/);
  if (!m) return null;
  try {
    const obj = JSON.parse(m[0]);
    if (obj && Array.isArray(obj.claims) && obj.claims.length > 0) {
      return {
        stance_strength: typeof obj.stance_strength === "number" ? obj.stance_strength : undefined,
        summary: obj.summary || "",
        claims: obj.claims,
      };
    }
  } catch {
    // not JSON → fall through
  }
  return null;
}

/** 从 Markdown 中提取 **标题** 段落 */
function parseSections(md: string): { title: string; body: string }[] {
  const sections: { title: string; body: string }[] = [];
  const re = /^\*\*(.+?)\*\*$/gm;
  const matches = [...md.matchAll(re)];
  for (let i = 0; i < matches.length; i++) {
    const title = matches[i][1].trim();
    const start = matches[i].index! + matches[i][0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index! : md.length;
    const body = md.slice(start, end).trim();
    if (body) sections.push({ title, body });
  }
  return sections;
}

/** 从 strategy agent JSON 中提取裁决 */
function parseRuling(strategyContent: string) {
  const ruling: {
    recommendation?: string;
    confidence?: number;
    reasoning?: string;
    weight_summary?: string;
  } = {};
  try {
    const m = strategyContent.match(/\{[\s\S]*\}/);
    if (m) {
      const obj = JSON.parse(m[0]);
      ruling.recommendation = obj.recommendation;
      ruling.confidence = obj.confidence_score;
      ruling.reasoning = obj.reasoning;
      ruling.weight_summary = obj.weight_summary;
    }
  } catch {
    ruling.reasoning = strategyContent.slice(0, 300);
  }
  return ruling;
}

function RulingBadge({ rec }: { rec?: string }) {
  if (!rec) return null;
  const color =
    rec === "Buy" ? "#22c55e" :
    rec === "Sell" ? "#ef4444" :
    rec === "Hold" ? "#f59e0b" : "#6b7280";
  const label =
    rec === "Buy" ? "买入" :
    rec === "Sell" ? "卖出" :
    rec === "Hold" ? "持有" : rec;
  return (
    <span className="dp-ruling-badge" style={{ color, background: `${color}14`, border: `1px solid ${color}33` }}>
      {label}
    </span>
  );
}

/* ── 单条 claim 卡片（结构化输出） ── */
function ClaimCard({ claim, tone }: { claim: DebateClaim; tone: "bull" | "bear" }) {
  const confColor =
    claim.confidence >= 80 ? "#22c55e" :
    claim.confidence >= 60 ? "#f59e0b" : "#ef4444";

  return (
    <div className={`dp-claim-card ${tone}`}>
      <p className="dp-claim-text">{claim.text}</p>
      <div className="dp-claim-meta">
        <span className="dp-claim-conf" style={{ color: confColor }}>
          置信度 {claim.confidence}%
        </span>
        {claim.sources.length > 0 && (
          <span className="dp-claim-sources">
            {claim.sources.map((s) => (
              <span key={s} className="dp-claim-source-badge">{s}</span>
            ))}
          </span>
        )}
        {claim.supporting_fields.length > 0 && (
          <span className="dp-claim-fields">
            {claim.supporting_fields.join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}

/* ── 姿势强度条 ── */
function StanceBar({ strength, label }: { strength: number; label: string }) {
  const color = strength >= 70 ? "#22c55e" : strength >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div className="dp-stance">
      <span className="dp-stance-label">{label}信念</span>
      <div className="dp-stance-bar-wrap">
        <div
          className="dp-stance-bar"
          style={{ width: `${strength}%`, background: color }}
        />
      </div>
      <span className="dp-stance-val" style={{ color }}>{strength}%</span>
    </div>
  );
}

export default function DebatePanel({ agents, evidence, guard, recommendation }: DebatePanelProps) {
  const bullContent = useMemo(() => getContent(agents, "bull_researcher"), [agents]);
  const bearContent = useMemo(() => getContent(agents, "bear_researcher"), [agents]);
  const strategyContent = useMemo(() => getContent(agents, "strategy_expert"), [agents]);

  // 尝试结构化解析
  const bullStructured = useMemo(() => tryParseDebateData(bullContent), [bullContent]);
  const bearStructured = useMemo(() => tryParseDebateData(bearContent), [bearContent]);

  // 向后兼容：无结构化数据时按 section 解析
  const bullSections = useMemo(
    () => (bullStructured ? [] : parseSections(bullContent)),
    [bullStructured, bullContent],
  );
  const bearSections = useMemo(
    () => (bearStructured ? [] : parseSections(bearContent)),
    [bearStructured, bearContent],
  );

  const ruling = useMemo(() => parseRuling(strategyContent), [strategyContent]);

  const hasBull = bullContent.trim().length > 0;
  const hasBear = bearContent.trim().length > 0;
  const hasRuling = ruling.recommendation || ruling.reasoning || strategyContent.trim().length > 0;
  const hasAny = hasBull || hasBear || hasRuling;

  const evidenceSources = useMemo(() => {
    const facts = evidence?.facts ?? [];
    return [...new Set(facts.map((f) => f.source || "unknown"))].sort();
  }, [evidence]);

  const guardConfidence = guard?.confidence_score ?? evidence?.evidence_score ?? 0;
  const confidenceLabel = guardConfidence >= 80 ? "高置信度" : guardConfidence >= 60 ? "中置信度" : "低置信度";
  const confidenceColor = guardConfidence >= 80 ? "#22c55e" : guardConfidence >= 60 ? "#f59e0b" : "#ef4444";

  if (!hasAny) {
    return (
      <div className="debate-panel">
        <div className="dp-header">
          <Gavel size={17} />
          <span>多空博弈</span>
        </div>
        <div className="dp-empty">
          <span>辩论尚未开始或已跳过</span>
          <span className="dp-empty-sub">证据不足无法进行双反对抗性分析</span>
        </div>
      </div>
    );
  }

  return (
    <div className="debate-panel">
      <div className="dp-header">
        <Gavel size={17} />
        <span>多空博弈</span>
        {hasRuling && <RulingBadge rec={ruling.recommendation} />}
        {guardConfidence > 0 && (
          <span className="dp-confidence" style={{ color: confidenceColor }}>
            {confidenceLabel} ({guardConfidence}/100)
          </span>
        )}
      </div>

      {evidenceSources.length > 0 && (
        <div className="dp-sources">
          <Database size={11} />
          {evidenceSources.map((s) => (
            <span key={s} className="dp-source-badge">{s}</span>
          ))}
        </div>
      )}

      {/* Bull vs Bear 双栏 */}
      <div className="dp-columns">
        {/* ── Bull 卡片 ── */}
        <div className="dp-card bull">
          <div className="dp-card-hd">
            <TrendingUp size={16} color="#22c55e" />
            <span className="dp-card-title bull">多方论点</span>
            <span className="dp-card-badge bull">Bull</span>
          </div>
          {hasBull ? (
            <div className="dp-card-body">
              {bullStructured && bullStructured.stance_strength !== undefined && (
                <StanceBar strength={bullStructured.stance_strength} label="多方" />
              )}
              {bullStructured ? (
                bullStructured.claims.map((c, i) => (
                  <ClaimCard key={i} claim={c} tone="bull" />
                ))
              ) : bullSections.length > 0 ? (
                bullSections.map((s, i) => (
                  <div key={i} className="dp-section">
                    <div className="dp-section-title bull">{s.title}</div>
                    <p className="dp-section-body">{s.body}</p>
                  </div>
                ))
              ) : (
                <p className="dp-card-text">{bullContent}</p>
              )}
            </div>
          ) : (
            <div className="dp-card-empty">多方论点暂未输出</div>
          )}
        </div>

        {/* ── Bear 卡片 ── */}
        <div className="dp-card bear">
          <div className="dp-card-hd">
            <TrendingDown size={16} color="#ef4444" />
            <span className="dp-card-title bear">空方论点</span>
            <span className="dp-card-badge bear">Bear</span>
          </div>
          {hasBear ? (
            <div className="dp-card-body">
              {bearStructured && bearStructured.stance_strength !== undefined && (
                <StanceBar strength={bearStructured.stance_strength} label="空方" />
              )}
              {bearStructured ? (
                bearStructured.claims.map((c, i) => (
                  <ClaimCard key={i} claim={c} tone="bear" />
                ))
              ) : bearSections.length > 0 ? (
                bearSections.map((s, i) => (
                  <div key={i} className="dp-section">
                    <div className="dp-section-title bear">{s.title}</div>
                    <p className="dp-section-body">{s.body}</p>
                  </div>
                ))
              ) : (
                <p className="dp-card-text">{bearContent}</p>
              )}
            </div>
          ) : (
            <div className="dp-card-empty">空方论点暂未输出</div>
          )}
        </div>
      </div>

      {/* ── 裁决摘要 ── */}
      {hasRuling && (
        <div className="dp-ruling">
          <div className="dp-ruling-hd">
            <Target size={14} color="#a78bfa" />
            <span>策略裁决</span>
          </div>
          {ruling.recommendation && (
            <div className="dp-ruling-row">
              <span className="dp-ruling-label">结论</span>
              <RulingBadge rec={ruling.recommendation} />
              {ruling.confidence && (
                <span className="dp-ruling-score">置信度 {ruling.confidence}/100</span>
              )}
            </div>
          )}
          {ruling.weight_summary && (
            <div className="dp-ruling-row">
              <span className="dp-ruling-label">权重分配</span>
              <span className="dp-ruling-text">{ruling.weight_summary}</span>
            </div>
          )}
          {ruling.reasoning && (
            <div className="dp-ruling-reasoning">
              <span className="dp-ruling-label">分析过程</span>
              <p className="dp-ruling-text">{ruling.reasoning}</p>
            </div>
          )}
          {!ruling.recommendation && recommendation && (
            <div className="dp-ruling-reasoning">
              <span className="dp-ruling-label">综合结论</span>
              <p className="dp-ruling-text">{recommendation}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
