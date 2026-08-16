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

/** 从文本中提取 JSON 对象（优先最外层完整 JSON） */
function extractBalancedJson(text: string, _preference: "first" | "last" = "first"): string | null {
  const starts: number[] = [];
  for (let i = 0; i < text.length; i++) {
    if (text[i] === "{") starts.push(i);
  }
  const ordered = _preference === "last" ? [...starts].reverse() : starts;
  // 从最外层（第一个 {）开始匹配，避免嵌套对象干扰
  for (const start of ordered) {
    let depth = 0;
    for (let j = start; j < text.length; j++) {
      if (text[j] === "{") depth++;
      else if (text[j] === "}") depth--;
      if (depth === 0) return text.slice(start, j + 1);
    }
  }
  return null;
}

function toStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => String(v)).filter(Boolean);
  if (typeof value === "string" && value.trim()) {
    return value.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
  }
  return [];
}

function normalizeClaim(raw: unknown): DebateClaim | null {
  if (!raw || typeof raw !== "object") return null;
  const c = raw as Record<string, unknown>;
  const text = String(c.text ?? "").trim();
  if (!text) return null;
  const confidenceRaw = c.confidence;
  const confidence =
    typeof confidenceRaw === "number"
      ? confidenceRaw
      : Number.parseFloat(String(confidenceRaw ?? "50")) || 50;
  return {
    text,
    confidence: Math.min(100, Math.max(0, confidence)),
    sources: toStringList(c.sources),
    supporting_fields: toStringList(c.supporting_fields),
  };
}

/** 尝试从 agent 内容解析 JSON，返回结构化数据或 null */
function tryParseDebateData(content: string): DebateStructuredData | null {
  const jsonText = extractBalancedJson(content.trim());
  if (!jsonText) return null;
  try {
    const obj = JSON.parse(jsonText) as Record<string, unknown>;
    const rawClaims = Array.isArray(obj.claims) ? obj.claims : [];
    const claims = rawClaims
      .map(normalizeClaim)
      .filter((c): c is DebateClaim => c !== null);

    if (claims.length === 0) {
      const summary = String(obj.summary ?? "").trim();
      if (!summary) return null;
      return {
        stance_strength: typeof obj.stance_strength === "number" ? obj.stance_strength : undefined,
        summary,
        claims: [],
      };
    }

    return {
      stance_strength: typeof obj.stance_strength === "number" ? obj.stance_strength : undefined,
      summary: String(obj.summary ?? ""),
      claims,
    };
  } catch {
    return null;
  }
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

/** 从 Markdown 表格中提取 key 对应的值 */
function extractTableValue(md: string, key: string): string | undefined {
  // 匹配 | **key** | 内容 |
  const re = new RegExp(`\\|\\s*\\*\\*${key}\\*\\*\\s*\\|\\s*(.+?)\\s*\\|`, "im");
  const m = md.match(re);
  if (!m) return undefined;
  // 去掉可能的内嵌 markdown 标记（**粗体**、emoji等）取纯文本
  return m[1].replace(/\*\*/g, "").replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2700}-\u{27BF}]/gu, "").trim();
}

/** 从中文 Markdown 标题后提取段落内容 */
function extractSectionBody(md: string, heading: string): string | undefined {
  const re = new RegExp(`###\\s+${heading}\\s*\\n+([\\s\\S]*?)(?=\\n###\\s|\\n---|$)`, "im");
  const m = md.match(re);
  return m ? m[1].trim() : undefined;
}

/** 中文建议 → 英文枚举映射 */
function recCnToEn(label: string): string | undefined {
  const map: Record<string, string> = { "买入": "Buy", "卖出": "Sell", "持有": "Hold", "暂无法评估": "N/A" };
  return map[label] ?? (label in map ? undefined : label);
}

function parseMarkdownRuling(md: string) {
  // 优先按新中文格式解析
  const cnRec = extractTableValue(md, "最终建议");
  const cnConf = extractTableValue(md, "置信度评分");
  const cnReasoning = extractSectionBody(md, "决策推理");
  const cnWeight = extractSectionBody(md, "因子权重分配");

  if (cnRec || cnConf || cnReasoning || cnWeight) {
    const confNum = cnConf ? Number.parseFloat(cnConf) : undefined;
    return {
      recommendation: cnRec ? recCnToEn(cnRec) : undefined,
      confidence: Number.isFinite(confNum) ? confNum : undefined,
      reasoning: cnReasoning,
      weight_summary: cnWeight,
    };
  }

  // 回退旧英文格式
  const get = (key: string) => {
    const re = new RegExp(`\\*\\*${key}\\*\\*:\\s*(.+)$`, "im");
    const m = md.match(re);
    return m ? m[1].trim() : undefined;
  };
  const confRaw = get("Confidence Score");
  const confidence = confRaw ? Number.parseFloat(confRaw) : undefined;
  return {
    recommendation: get("Recommendation"),
    confidence: Number.isFinite(confidence) ? confidence : undefined,
    reasoning: get("Reasoning"),
    weight_summary: get("Weight Summary"),
  };
}

/** 从 strategy agent JSON 或 Markdown 中提取裁决 */
function parseRuling(strategyContent: string) {
  const ruling: {
    recommendation?: string;
    confidence?: number;
    reasoning?: string;
    weight_summary?: string;
  } = {};

  const jsonText = extractBalancedJson(strategyContent.trim(), "last");
  if (jsonText) {
    try {
      const obj = JSON.parse(jsonText) as Record<string, unknown>;
      ruling.recommendation = typeof obj.recommendation === "string" ? obj.recommendation : undefined;
      const conf = obj.confidence_score;
      ruling.confidence = typeof conf === "number" ? conf : Number.parseFloat(String(conf ?? ""));
      if (!Number.isFinite(ruling.confidence)) ruling.confidence = undefined;
      const reasoning = obj.reasoning ?? obj.warning;
      ruling.reasoning = typeof reasoning === "string" ? reasoning : undefined;
      ruling.weight_summary = typeof obj.weight_summary === "string" ? obj.weight_summary : undefined;
      if (ruling.recommendation || ruling.reasoning) return ruling;
    } catch {
      // fall through to markdown parser
    }
  }

  const fromMd = parseMarkdownRuling(strategyContent);
  if (fromMd.recommendation || fromMd.reasoning) return fromMd;
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
                <>
                  {bullStructured.summary && bullStructured.claims.length === 0 && (
                    <p className="dp-section-body">{bullStructured.summary}</p>
                  )}
                  {bullStructured.claims.map((c, i) => (
                    <ClaimCard key={i} claim={c} tone="bull" />
                  ))}
                </>
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
                <>
                  {bearStructured.summary && bearStructured.claims.length === 0 && (
                    <p className="dp-section-body">{bearStructured.summary}</p>
                  )}
                  {bearStructured.claims.map((c, i) => (
                    <ClaimCard key={i} claim={c} tone="bear" />
                  ))}
                </>
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
          {!ruling.recommendation && !ruling.reasoning && (
            <div className="dp-ruling-reasoning">
              <span className="dp-ruling-label">策略裁决</span>
              <p className="dp-ruling-text">暂未生成策略裁决数据</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
