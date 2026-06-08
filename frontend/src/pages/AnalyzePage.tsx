import { Activity, ArrowRight, Check, ChevronRight, FileText, X, Zap } from "lucide-react";
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
import { useTranslation } from "../i18n";
import { createSession } from "../services/api";
import { streamAnalyze, StreamEvent, GuardCheck } from "../services/sse";

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
  status: "idle" | "running" | "done";
  content: string;
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
  statusLabel: (status: "idle" | "running" | "done") => string;
  clickToView: string;
  descStandingBy: string;
  descReady: string;
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
  onSelect,
}: AgentCardProps) {
  const status = live ? live.status : "idle";
  const hasContent = Boolean(live?.content?.trim());
  const desc = hasContent
    ? live!.content.slice(-120).replace(/\n/g, " ")
    : running
      ? descStandingBy
      : descReady;
  const LucideIcon = def.lucide;

  return (
    <button
      type="button"
      className={`agent-grid-card agent-grid-card-btn ${status} ${isSelected ? "selected" : ""} ${hasContent || status !== "idle" ? "has-output" : ""}`}
      style={{ "--agent-color": def.color } as React.CSSProperties}
      onClick={() => onSelect(def.id)}
      aria-pressed={isSelected}
    >
      <div className="agc-top">
        <div className="agc-icon-wrap" style={{ background: `${def.color}14` }}>
          <LucideIcon size={20} style={{ color: def.color }} />
        </div>
        <span className={`agc-status-tag ${status}`}>{statusLabel(status)}</span>
      </div>
      <div className="agc-name">{def.label}</div>
      <div className="agc-role">{def.role}</div>
      <div className="agc-desc">{desc}</div>
      {(hasContent || status === "done") && <div className="agc-hint">{clickToView}</div>}
      {status === "running" && <div className="agc-progress" />}
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
    try {
      const sessionId = await ensureSession();
      await streamAnalyze(
        {
          session_id: sessionId,
          message,
          stock_symbol: stockSymbol,
          language: detectLanguage(message),
        },
        (evt: StreamEvent) => {
          if (evt.event === "agent_start") {
            setAgents((prev) =>
              upsertAgent(prev, evt.data.agent, {
                label: evt.data.label,
                icon: evt.data.icon,
                status: "running",
                content: "",
              }),
            );
          }
          if (evt.event === "agent_output") {
            setAgents((prev) =>
              upsertAgent(prev, evt.data.agent, {
                status: "running",
                content:
                  (prev.find((a) => a.agent === evt.data.agent)?.content ?? "") + evt.data.content,
              }),
            );
          }
          if (evt.event === "agent_done") {
            setAgents((prev) => upsertAgent(prev, evt.data.agent, { status: "done" }));
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

  function statusLabel(status: "idle" | "running" | "done") {
    if (status === "running") return t("analyze.statusAnalyzing");
    if (status === "done") return t("analyze.statusComplete");
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
                </div>
              </div>
            )}
          </section>

          <section className="card">
            <h3 className="card-title">{t("analyze.finalReport")}</h3>
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
