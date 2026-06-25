import { Activity, ArrowRight, Check, ChevronRight, Download, FileDown, FileText, X, Zap } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AGENT_VISUAL,
  CORE_AGENT_IDS,
  ENHANCEMENT_AGENT_IDS,
  SYSTEM_NODE_IDS,
  buildReportFromAgents,
  isPlaceholderReport,
  isSystemNode,
  isWorkflowNodeId,
  type WorkflowNodeId,
} from "../constants/agents";
import MarkdownContent from "../components/MarkdownContent";
import StockOverviewPanel from "../components/StockOverviewPanel";
import ValuationSummaryCard from "../components/ValuationSummaryCard";
import FinancialTrendsPanel from "../components/FinancialTrendsPanel";
import RiskGauge from "../components/RiskGauge";
import { generateMarkdownReport, downloadMarkdownReport, downloadPDFReport } from "../services/reportExporter";
import DebatePanel from "../components/DebatePanel";
import { useTranslation } from "../i18n";
import { createSession } from "../services/api";
import { streamAnalyze, StreamEvent, GuardCheck, EvidencePacketData, TargetPriceData, RiskLevelData, parseRiskLevelFromContent } from "../services/sse";

function detectLanguage(text: string): string {
  const stripped = text.replace(/\s/g, "");
  if (!stripped) return "en";
  const cjkChars = stripped.match(/[\u4e00-\u9fff\u3400-\u4dbf]/g) || [];
  const cjkRatio = cjkChars.length / stripped.length;
  if (cjkRatio < 0.25) return "en";
  const yuePattern = /[嘅咁哋啲佢嚟喺冧冇乜嘢唔係咩吓呢畀咗啱嗰喎嘞瞓攰搵睇嘥攞㗎啫啩噃嚿孭踎嗌㩒抦]/;
  return yuePattern.test(text) ? "yue" : "zh";
}

type AgentStatus = {
  agent: string;
  label: string;
  icon: string;
  status: "idle" | "running" | "done" | "error" | "skipped";
  content: string;
  startedAt?: number;
  finishedAt?: number;
  /** 核心结论（由后端 LLM 提炼，agent_core_conclusion SSE 事件推送） */
  coreConclusion?: string;
  /** 结论情绪标签：positive / negative / neutral */
  conclusionSentiment?: "positive" | "negative" | "neutral";
  /** 结论置信度 0-100 */
  conclusionConfidence?: number;
};

type NodeDef = {
  id: WorkflowNodeId;
  label: string;
  role: string;
  icon: string;
  lucide: (typeof AGENT_VISUAL)[WorkflowNodeId]["lucide"];
  color: string;
};

function upsertAgent(
  prev: AgentStatus[],
  agent: string,
  patch: Partial<AgentStatus> & { label?: string; icon?: string },
): AgentStatus[] {
  const exists = prev.find((a) => a.agent === agent);
  if (exists) {
    return prev.map((a) => (a.agent === agent ? { ...a, ...patch } : a));
  }
  return [
    ...prev,
    {
      agent,
      label: patch.label ?? agent,
      icon: patch.icon ?? "🤖",
      status: patch.status ?? "running",
      content: patch.content ?? "",
    },
  ];
}

function buildNodeDef(id: WorkflowNodeId, t: (key: string) => string): NodeDef {
  const visual = AGENT_VISUAL[id];
  const prefix = isSystemNode(id) ? "analyze.nodes" : "analyze.agents";
  return {
    id,
    label: t(`${prefix}.${id}.label`),
    role: t(`${prefix}.${id}.role`),
    ...visual,
  };
}

type AgentCardProps = {
  def: NodeDef;
  live?: AgentStatus;
  running: boolean;
  isSelected: boolean;
  statusLabel: (status: AgentStatus["status"]) => string;
  clickToView: string;
  descStandingBy: string;
  descReady: string;
  skippedHint: string;
  onSelect: (id: WorkflowNodeId) => void;
};

function AgentCard({
  def,
  live,
  running,
  isSelected,
  statusLabel,
  clickToView,
  descStandingBy,
  descReady,
  skippedHint,
  onSelect,
}: AgentCardProps) {
  const status = live ? live.status : "idle";
  const hasContent = Boolean(live?.content?.trim());
  const isCurrentlyRunning = running && status === "running";
  const desc = hasContent
    ? live!.content.slice(-120).replace(/\n/g, " ")
    : running
      ? descStandingBy
      : descReady;

  // 计算耗时
  const elapsed = useMemo(() => {
    if (!live?.startedAt) return "";
    const end = live.finishedAt ?? Date.now();
    const ms = end - live.startedAt;
    if (ms < 1000) return "< 1s";
    if (ms < 60000) return `${Math.round(ms / 1000)}s`;
    const mins = Math.floor(ms / 60000);
    const secs = Math.round((ms % 60000) / 1000);
    return `${mins}m ${secs}s`;
  }, [live?.startedAt, live?.finishedAt]);

  // 动态刷新 running 状态的耗时
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!isCurrentlyRunning) return;
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, [isCurrentlyRunning]);

  // force re-compute on tick
  const displayElapsed = isCurrentlyRunning
    ? (() => {
        if (!live?.startedAt) return "";
        const ms = Date.now() - live.startedAt;
        if (ms < 1000) return "< 1s";
        if (ms < 60000) return `${Math.round(ms / 1000)}s`;
        const mins = Math.floor(ms / 60000);
        const secs = Math.round((ms % 60000) / 1000);
        return `${mins}m ${secs}s`;
      })()
    : elapsed;

  const LucideIcon = def.lucide;

  const coreConclusion = live?.coreConclusion;
  const conclusionSentiment = live?.conclusionSentiment;
  const conclusionConf = live?.conclusionConfidence;

  const sentimentColor =
    conclusionSentiment === "positive"
      ? "#22c55e"
      : conclusionSentiment === "negative"
        ? "#ef4444"
        : "#f59e0b";

  const sentimentLabel =
    conclusionSentiment === "positive"
      ? "正面"
      : conclusionSentiment === "negative"
        ? "负面"
        : "中性";

  return (
    <button
      type="button"
      className={`agent-grid-card agent-grid-card-btn ${status} ${isSelected ? "selected" : ""} ${hasContent || status !== "idle" ? "has-output" : ""} ${isCurrentlyRunning ? "active-running" : ""}`}
      style={{ "--agent-color": def.color } as React.CSSProperties}
      onClick={() => onSelect(def.id)}
      aria-pressed={isSelected}
    >
      <div className="agc-top">
        <div className={`agc-icon-wrap ${isCurrentlyRunning ? "agc-icon-pulse" : ""}`} style={{ background: `${def.color}14` }}>
          <LucideIcon size={20} style={{ color: def.color }} />
        </div>
        <span className={`agc-status-tag ${status}`}>{statusLabel(status)}</span>
        {displayElapsed && status !== "idle" && (
          <span className="agc-elapsed">{displayElapsed}</span>
        )}
      </div>
      <div className="agc-name">{def.label}</div>
      <div className="agc-role">{def.role}</div>
      {coreConclusion && (
        <div
          className="agc-conclusion"
          style={{
            background: `${sentimentColor}10`,
            borderLeft: `3px solid ${sentimentColor}`,
          }}
        >
          <span
            className="agc-conclusion-tag"
            style={{
              background: `${sentimentColor}22`,
              color: sentimentColor,
            }}
          >
            {sentimentLabel}
            {conclusionConf !== undefined && ` ${conclusionConf}%`}
          </span>
          <span className="agc-conclusion-text">{coreConclusion}</span>
        </div>
      )}
      <div className={`agc-desc ${hasContent ? "has-content" : ""}`}>
        {status === "error" && live?.content ? (
          <span className="agc-error-text">{live.content}</span>
        ) : status === "skipped" ? (
          <span className="agc-skipped-text">{skippedHint}</span>
        ) : (
          desc
        )}
      </div>
      {(hasContent || status === "done") && <div className="agc-hint">{clickToView}</div>}
      {isCurrentlyRunning && (
        <div className="agc-loading-bar">
          <div className="agc-loading-bar-inner" />
        </div>
      )}
    </button>
  );
}

export default function AnalyzePage() {
  const { t, locale } = useTranslation();
  const [stockSymbol, setStockSymbol] = useState("TSLA");
  const [message, setMessage] = useState(() => t("analyze.defaultPrompt"));
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<WorkflowNodeId | null>(null);
  const [report, setReport] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [guardCheck, setGuardCheck] = useState<GuardCheck | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [evidencePacket, setEvidencePacket] = useState<EvidencePacketData | null>(null);
  const [targetPrice, setTargetPrice] = useState<TargetPriceData | null>(null);
  const [riskLevel, setRiskLevel] = useState<RiskLevelData | null>(null);
  const prevDefaultPrompt = useRef(t("analyze.defaultPrompt"));

  useEffect(() => {
    const nextDefault = t("analyze.defaultPrompt");
    setMessage((current) => (current === prevDefaultPrompt.current ? nextDefault : current));
    prevDefaultPrompt.current = nextDefault;
  }, [locale, t]);

  const coreRegistry = useMemo(
    () => CORE_AGENT_IDS.map((id) => buildNodeDef(id, t)),
    [t],
  );

  const activeEnhancementIds = useMemo(
    () => ENHANCEMENT_AGENT_IDS.filter((id) => agents.some((a) => a.agent === id)),
    [agents],
  );

  const enhancementRegistry = useMemo(
    () => activeEnhancementIds.map((id) => buildNodeDef(id, t)),
    [activeEnhancementIds, t],
  );

  const showSystemPipeline = useMemo(
    () => running || SYSTEM_NODE_IDS.some((id) => agents.some((a) => a.agent === id)),
    [running, agents],
  );

  const allRegistry = useMemo(
    () => [...coreRegistry, ...enhancementRegistry, ...SYSTEM_NODE_IDS.map((id) => buildNodeDef(id, t))],
    [coreRegistry, enhancementRegistry, t],
  );

  const canRun = useMemo(() => !running && message.trim().length > 0, [running, message]);

  const selectedContent = selectedAgentId
    ? (agents.find((a) => a.agent === selectedAgentId)?.content ?? "")
    : "";

  const selectedLabel =
    allRegistry.find((a) => a.id === selectedAgentId)?.label ?? selectedAgentId ?? "";

  async function ensureSession(): Promise<string> {
    if (currentSessionId) return currentSessionId;
    const created = await createSession(t("analyze.sessionTitle", { symbol: stockSymbol }));
    const sessionId = created.id;
    setCurrentSessionId(sessionId);
    return sessionId;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canRun) return;
    setRunning(true);
    setError("");
    setAgents([]);
    setSelectedAgentId(null);
    setReport("");
    setRecommendation("");
    setGuardCheck(null);
    setEvidencePacket(null);
    setTargetPrice(null);
    setRiskLevel(null);
    try {
      const sessionId = await ensureSession();
      await streamAnalyze(
        {
          session_id: sessionId,
          message,
          stock_symbol: stockSymbol.trim().toUpperCase(),
          language: detectLanguage(message),
        },
        (evt: StreamEvent) => {
          if (evt.event === "evidence_packet") {
            setEvidencePacket(evt.data);
          }
          if (evt.event === "target_price") {
            setTargetPrice(evt.data);
          }
          if (evt.event === "risk_level") {
            setRiskLevel(evt.data);
          }
          if (evt.event === "agent_start") {
            const now = Date.now();
            setAgents((prev) =>
              upsertAgent(prev, evt.data.agent, {
                label: evt.data.label,
                icon: evt.data.icon,
                status: "running",
                content: "",
                startedAt: now,
                finishedAt: undefined,
              }),
            );
          }
          if (evt.event === "agent_output") {
            setAgents((prev) =>
              upsertAgent(prev, evt.data.agent, {
                status: "running",
                content: evt.data.content,
              }),
            );
            if (evt.data.agent === "risk_expert") {
              const parsed = parseRiskLevelFromContent(evt.data.content);
              if (parsed) setRiskLevel(parsed);
            }
          }
          if (evt.event === "agent_core_conclusion") {
            setAgents((prev) =>
              upsertAgent(prev, evt.data.agent, {
                coreConclusion: evt.data.core_conclusion,
                conclusionSentiment: evt.data.conclusion_sentiment,
                conclusionConfidence: evt.data.confidence_score,
              }),
            );
          }
          if (evt.event === "agent_done") {
            setAgents((prev) =>
              upsertAgent(prev, evt.data.agent, {
                status: "done",
                finishedAt: Date.now(),
                // 用后端 duration_ms 覆盖 startedAt 以显示服务端真实耗时
                startedAt: evt.data.duration_ms !== undefined
                  ? Date.now() - evt.data.duration_ms
                  : undefined,
              }),
            );
          }
          if (evt.event === "agent_error") {
            setAgents((prev) =>
              upsertAgent(prev, evt.data.agent, {
                label: evt.data.label,
                icon: evt.data.icon,
                status: "error",
                content: evt.data.message,
                startedAt: evt.data.duration_ms !== undefined
                  ? Date.now() - evt.data.duration_ms
                  : undefined,
                finishedAt: Date.now(),
              }),
            );
          }
          if (evt.event === "agent_skipped") {
            setAgents((prev) =>
              upsertAgent(prev, evt.data.agent, {
                label: evt.data.label,
                icon: evt.data.icon,
                status: "skipped",
                content: "",
                finishedAt: Date.now(),
              }),
            );
          }
          if (evt.event === "analysis_complete") {
            setAgents((prev) => {
              let nextReport = evt.data.final_report ?? "";
              if (isPlaceholderReport(nextReport)) {
                const deduped = prev.filter(
                  (a, i, arr) => arr.findIndex((x) => x.agent === a.agent) === i,
                );
                const combined = buildReportFromAgents(
                  deduped.map((a) => ({ agent: a.agent, label: a.label, content: a.content })),
                );
                if (combined) nextReport = combined;
                else if (evt.data.recommendation) nextReport = evt.data.recommendation;
              }
              setReport(nextReport);
              setRecommendation(evt.data.recommendation ?? "");
              if (evt.data.guard_check) {
                setGuardCheck(evt.data.guard_check);
              }
              if (evt.data.target_price) {
                setTargetPrice(evt.data.target_price);
              }
              if (evt.data.risk_level) {
                setRiskLevel(evt.data.risk_level);
              }
              return prev;
            });
          }
          if (evt.event === "error") {
            setError(evt.data.detail);
          }
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("errors.analyzeFailed"));
    } finally {
      setRunning(false);
    }
  }

  function statusLabel(status: "idle" | "running" | "done" | "error" | "skipped") {
    if (status === "running") return t("analyze.statusAnalyzing");
    if (status === "done") return t("analyze.statusComplete");
    if (status === "error") return t("analyze.statusError");
    if (status === "skipped") return t("analyze.statusSkipped");
    return t("analyze.statusStandby");
  }

  function handleAgentClick(id: WorkflowNodeId) {
    setSelectedAgentId((current) => (current === id ? null : id));
  }

  function renderAgentGrid(defs: NodeDef[]) {
    return (
      <div className="agent-grid-v2">
        {defs.map((def) => (
          <AgentCard
            key={def.id}
            def={def}
            live={agents.find((a) => a.agent === def.id)}
            running={running}
            isSelected={selectedAgentId === def.id}
            statusLabel={statusLabel}
            clickToView={t("analyze.clickToView")}
            descStandingBy={t("analyze.descStandingBy")}
            descReady={t("analyze.descReady")}
            skippedHint={t("analyze.skippedHint")}
            onSelect={handleAgentClick}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="page">
      <header className="analyze-page-header">
        <div className="analyze-header-left">
          <span className="analyze-header-title">
            <Zap size={18} className="analyze-header-icon" />
            {t("analyze.title")}
          </span>
          <span className="analyze-header-sub">{t("analyze.subtitle")}</span>
        </div>
        <div className="analyze-header-right">
          <span className="analyze-badge">{t("analyze.badge")}</span>
        </div>
      </header>

      <div className="analyze-layout">
        <div className="analyze-side">
          <section className="card">
            <h2 className="card-title">{t("analyze.researchInput")}</h2>
            <form onSubmit={handleSubmit} className="analyze-form">
              <div className="analyze-input-group">
                <label>{t("analyze.stockSymbol")}</label>
                <input
                  value={stockSymbol}
                  onChange={(e) => setStockSymbol(e.target.value.toUpperCase())}
                  placeholder={t("analyze.stockPlaceholder")}
                />
              </div>
              <div className="analyze-input-group">
                <label>{t("analyze.researchPrompt")}</label>
                <textarea
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder={t("analyze.promptPlaceholder")}
                />
              </div>
              <button className="analyze-btn" type="submit" disabled={!canRun}>
                {running ? (
                  <>
                    <Activity size={16} />
                    {t("analyze.analyzing")}
                  </>
                ) : (
                  <>
                    {t("analyze.startAnalysis")}
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>
            {error ? <div className="error">{error}</div> : null}
          </section>
        </div>

        <div className="analyze-main">
          {/* 股票概览面板：放在主内容区顶部 */}
          {(evidencePacket || running) && (
            <section className="card">
              <StockOverviewPanel
                data={evidencePacket}
                stockSymbol={stockSymbol.trim().toUpperCase()}
              />
            </section>
          )}

          <section className="card">
            <div className="collab-header">
              <h3 className="card-title">{t("analyze.agentCollab")}</h3>
              <span className="collab-subtitle">{t("analyze.agentCollabSub")}</span>
            </div>

            {showSystemPipeline && (
              <div className="system-pipeline">
                <span className="system-pipeline-label">{t("analyze.systemPipeline")}</span>
                <div className="system-pipeline-track">
                  {SYSTEM_NODE_IDS.map((id, index) => {
                    const def = buildNodeDef(id, t);
                    const live = agents.find((a) => a.agent === id);
                    const status = live?.status ?? "idle";
                    const StepIcon = def.lucide;
                    return (
                      <div key={id} className="system-pipeline-step-wrap">
                        {index > 0 && <ChevronRight size={14} className="system-pipeline-arrow" />}
                        <button
                          type="button"
                          className={`system-pipeline-step ${status}`}
                          onClick={() => handleAgentClick(id)}
                          title={def.role}
                        >
                          <span className="system-step-icon">
                            {status === "done" ? (
                              <Check size={14} />
                            ) : (
                              <StepIcon size={14} />
                            )}
                          </span>
                          <span className="system-step-label">{def.label}</span>
                          <span className={`system-step-status ${status}`}>
                            {statusLabel(status)}
                          </span>
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="agent-tier">
              <div className="agent-tier-header">
                <h4>{t("analyze.coreAgents")}</h4>
                <span>{t("analyze.coreAgentsSub")}</span>
              </div>
              {renderAgentGrid(coreRegistry)}
            </div>

            {activeEnhancementIds.length > 0 && (
              <div className="agent-tier agent-tier-enhancement">
                <div className="agent-tier-header">
                  <h4>{t("analyze.enhancementAgents")}</h4>
                  <span>{t("analyze.enhancementAgentsSub")}</span>
                </div>
                {renderAgentGrid(enhancementRegistry)}
              </div>
            )}

            {selectedAgentId && isWorkflowNodeId(selectedAgentId) && (
              <div className="agent-detail-panel">
                <div className="agent-detail-header">
                  <h4>
                    {t("analyze.agentDetail")} — {selectedLabel}
                  </h4>
                  <button
                    type="button"
                    className="btn ghost agent-detail-close"
                    onClick={() => setSelectedAgentId(null)}
                  >
                    <X size={16} />
                    {t("analyze.closeDetail")}
                  </button>
                </div>
                <div className="agent-detail-body">
                  <MarkdownContent
                    content={selectedContent}
                    emptyFallback={t("analyze.noOutput")}
                  />
                  {/* 数据来源列表 */}
                  <AgentSources
                    agentId={selectedAgentId}
                    facts={evidencePacket?.facts ?? []}
                  />
                </div>
              </div>
            )}
          </section>

          {/* 财务基本面快照：只展示已有 facts，不启用多年度趋势图 */}
          {evidencePacket && (
            <section className="card">
              <FinancialTrendsPanel evidence={evidencePacket} />
            </section>
          )}

          {/* 多空博弈面板：Bull vs Bear 双栏 + 策略裁决 */}
          {evidencePacket && (
            <section className="card">
              <DebatePanel
                agents={agents}
                evidence={evidencePacket}
                guard={guardCheck}
                recommendation={recommendation}
              />
            </section>
          )}

          {/* 估值与结论摘要卡：分析完成后展示核心结论 */}
          {guardCheck && (
            <section className="card">
              <ValuationSummaryCard
                evidence={evidencePacket}
                guard={guardCheck}
                recommendation={recommendation}
                targetPrice={targetPrice}
                riskLevel={riskLevel}
              />
            </section>
          )}

          {/* 风险可视化仪表盘 */}
          {guardCheck && (
            <section className="card">
              <RiskGauge
                evidence={evidencePacket}
                guard={guardCheck}
                riskLevel={riskLevel}
              />
            </section>
          )}

          <section className="card">
            <div className="card-header-row">
              <h3 className="card-title">{t("analyze.finalReport")}</h3>
              {report && !running && (
                <div className="btn-export-group">
                  <button
                    className="btn-export"
                    onClick={() => {
                      const md = generateMarkdownReport({
                        stockSymbol,
                        finalReport: report,
                        recommendation,
                        evidence: evidencePacket,
                        guard: guardCheck,
                        riskLevel,
                        targetPrice,
                        agents,
                      });
                      downloadMarkdownReport(md, stockSymbol);
                    }}
                    title="导出 Markdown 报告"
                  >
                    <FileDown size={14} />
                    <span>.md</span>
                  </button>
                  <button
                    className="btn-export"
                    onClick={async () => {
                      await downloadPDFReport({
                        stockSymbol,
                        finalReport: report,
                        recommendation,
                        evidence: evidencePacket,
                        guard: guardCheck,
                        riskLevel,
                        targetPrice,
                        agents,
                      });
                    }}
                    title="导出 PDF 报告"
                  >
                    <Download size={14} />
                    <span>PDF</span>
                  </button>
                </div>
              )}
            </div>
            {!report && !running ? (
              <div className="analyze-empty">
                <FileText size={36} className="analyze-empty-icon" />
                <h4 className="analyze-empty-title">{t("analyze.emptyTitle")}</h4>
                <p className="analyze-empty-desc">{t("analyze.emptyDesc")}</p>
              </div>
            ) : (
              <>
                {report ? (
                  <div className="analyze-output">
                    <MarkdownContent content={report} />
                  </div>
                ) : (
                  <p className="analyze-output-placeholder">{t("analyze.inProgress")}</p>
                )}
                {recommendation && !isPlaceholderReport(report) && report !== recommendation && (
                  <div className="analyze-recommendation">
                    <h4>{t("analyze.recommendation")}</h4>
                    <MarkdownContent content={recommendation} />
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>

      {guardCheck && (
        <section className="card">
          <h3>
            🛡️ {t("analyze.guardTitle")}
            <span className={`guard-badge ${guardCheck.is_valid ? "guard-valid" : "guard-invalid"}`}>
              {guardCheck.is_valid ? t("analyze.guardPass") : t("analyze.guardFail")}
            </span>
          </h3>
          <div className="guard-grid">
            <div className="guard-stat">
              <span className="guard-label">{t("analyze.guardConfidence")}</span>
              <span className={`guard-score ${guardCheck.confidence_score >= 80 ? "score-high" : guardCheck.confidence_score >= 60 ? "score-mid" : "score-low"}`}>
                {guardCheck.confidence_score}/100
              </span>
            </div>
            <div className="guard-stat">
              <span className="guard-label">{t("analyze.guardValid")}</span>
              <span>{guardCheck.is_valid ? t("common.yes") : t("common.no")}</span>
            </div>
          </div>
          {guardCheck.issues.length > 0 && (
            <div className="guard-section">
              <h4>{t("analyze.guardIssues", { count: guardCheck.issues.length })}</h4>
              <ul>
                {guardCheck.issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {guardCheck.corrections.length > 0 && (
            <div className="guard-section">
              <h4>{t("analyze.guardCorrections", { count: guardCheck.corrections.length })}</h4>
              <ul>
                {guardCheck.corrections.map((corr, i) => (
                  <li key={i}>{corr}</li>
                ))}
              </ul>
            </div>
          )}
          {guardCheck.sources.length > 0 && (
            <div className="guard-section">
              <h4>{t("analyze.guardSources", { count: guardCheck.sources.length })}</h4>
              <ul className="guard-sources">
                {guardCheck.sources.map((src, i) => (
                  <li key={i}>{src}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="guard-section">
            <h4>{t("analyze.guardReasoning")}</h4>
            <div className="guard-reasoning">
              <MarkdownContent content={guardCheck.final_reasoning} />
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   Agent 详情 — 数据来源列表
   ══════════════════════════════════════════════════════════════════════ */

type AgentSourcesProps = {
  agentId: WorkflowNodeId;
  facts: EvidencePacketData["facts"];
};

// 各 Agent 关心的 fact field 映射
const AGENT_FACT_FIELDS: Record<string, string[]> = {
  market_data_expert: ["current_price", "price_change_pct", "ma_20", "ma_50", "ma_200", "rsi_14", "macd", "volatility_20d_annualized"],
  fundamental_expert: ["revenue", "total_revenue", "net_profit", "net_income", "eps", "eps_basic", "trailing_eps", "gross_margin", "net_margin", "operating_margin", "return_on_equity", "roe", "debt_to_assets", "debt_to_equity", "market_cap", "operating_cash_flow", "operating_cashflow", "free_cash_flow", "free_cashflow", "cash_position", "total_cash", "total_debt", "net_debt", "revenue_growth_yoy", "net_profit_growth_yoy", "eps_growth_yoy"],
  news_sentiment_expert: ["news_score", "news_sentiment"],
  risk_expert: ["volatility_20d_annualized", "sharpe_ratio_annual", "max_drawdown", "var_95_daily", "sortino_ratio_annual"],
  valuation_expert: ["pe_ratio", "pb_ratio", "ps_ratio", "ev_to_ebitda", "dividend_yield"],
  strategy_expert: ["current_price", "pe_ratio", "market_cap"],
  recommendation_agent: ["current_price", "market_cap", "pe_ratio"],
};

const FIELD_LABELS: Record<string, string> = {
  current_price: "当前价", price_change_pct: "涨跌幅",
  revenue: "营收", total_revenue: "营收", net_profit: "净利润", net_income: "净利润",
  eps: "EPS", eps_basic: "EPS", trailing_eps: "EPS",
  gross_margin: "毛利率", net_margin: "净利率", operating_margin: "营业利润率",
  return_on_equity: "ROE", roe: "ROE",
  debt_to_assets: "资产负债率", debt_to_equity: "负债权益比",
  market_cap: "市值", pe_ratio: "PE", pb_ratio: "PB",
  ps_ratio: "PS", ev_to_ebitda: "EV/EBITDA",
  dividend_yield: "股息率",
  rsi_14: "RSI(14)", macd: "MACD",
  volatility_20d_annualized: "波动率(20日)",
  ma_20: "MA20", ma_50: "MA50", ma_200: "MA200",
  sharpe_ratio_annual: "夏普比率", max_drawdown: "最大回撤",
  var_95_daily: "VaR(95%)", sortino_ratio_annual: "索提诺比率",
  news_score: "新闻评分", news_sentiment: "新闻情绪",
  operating_cash_flow: "经营现金流", operating_cashflow: "经营现金流",
  free_cash_flow: "自由现金流", free_cashflow: "自由现金流",
  cash_position: "现金储备", total_cash: "现金储备",
  total_debt: "总债务", net_debt: "净债务",
  revenue_growth_yoy: "营收增速", net_profit_growth_yoy: "净利润增速",
  net_income_growth_yoy: "净利润增速", eps_growth_yoy: "EPS增速",
};

function AgentSources({ agentId, facts }: AgentSourcesProps) {
  const relevantFields = AGENT_FACT_FIELDS[agentId] ?? [];
  const relevantFacts = facts.filter((f) => relevantFields.includes(f.field));

  if (relevantFacts.length === 0) return null;

  // 按 source 分组
  const bySource = new Map<string, typeof relevantFacts>();
  for (const f of relevantFacts) {
    const src = f.source || "unknown";
    if (!bySource.has(src)) bySource.set(src, []);
    bySource.get(src)!.push(f);
  }

  const sources = Array.from(bySource.entries());

  return (
    <div className="agent-sources">
      <div className="agent-sources-label">数据来源</div>
      <div className="agent-sources-list">
        {sources.map(([src, items]) => (
          <div key={src} className="agent-source-group">
            <span className="agent-source-name">{src}</span>
            <span className="agent-source-fields">
              {items.map((f) => FIELD_LABELS[f.field] || f.field).join(" · ")}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
