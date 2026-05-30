import { FormEvent, useMemo, useState } from "react";
import { createSession } from "../services/api";
import { streamAnalyze, StreamEvent, GuardCheck } from "../services/sse";

type AgentStatus = {
  agent: string;
  label: string;
  icon: string;
  status: "idle" | "running" | "done";
  content: string;
};

type NodeLog = {
  node: string;
  fields: string[];
};

export default function AnalyzePage() {
  const [stockSymbol, setStockSymbol] = useState("TSLA");
  const [message, setMessage] = useState("请全面分析该股票并给出中线投资建议");
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [report, setReport] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [guardCheck, setGuardCheck] = useState<GuardCheck | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  const canRun = useMemo(() => !running && message.trim().length > 0, [running, message]);

  async function ensureSession(): Promise<string> {
    if (currentSessionId) return currentSessionId;
    const created = await createSession(`Analysis ${stockSymbol}`);
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
        },
        (evt: StreamEvent) => {
          if (evt.event === "agent_start") {
            setAgents((prev) => {
              const exists = prev.find((a) => a.agent === evt.data.agent);
              if (exists) {
                return prev.map((a) => (a.agent === evt.data.agent ? { ...a, status: "running" as const, content: "" } : a));
              }
              return [...prev, { agent: evt.data.agent, label: evt.data.label, icon: evt.data.icon, status: "running", content: "" }];
            });
          }
          if (evt.event === "agent_output") {
            setAgents((prev) =>
              prev.map((a) => (a.agent === evt.data.agent ? { ...a, content: a.content + evt.data.content } : a)),
            );
          }
          if (evt.event === "agent_done") {
            setAgents((prev) =>
              prev.map((a) => (a.agent === evt.data.agent ? { ...a, status: "done" } : a)),
            );
          }
          if (evt.event === "analysis_complete") {
            setReport(evt.data.final_report ?? "");
            setRecommendation(evt.data.recommendation ?? "");
            if (evt.data.guard_check) {
              setGuardCheck(evt.data.guard_check);
            }
          }
          if (evt.event === "error") {
            setError(evt.data.detail);
          }
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyze failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="page">
      <section className="card">
        <h2>Real-time Analyze</h2>
        <form onSubmit={handleSubmit} className="form-grid">
          <label>
            Stock Symbol
            <input value={stockSymbol} onChange={(e) => setStockSymbol(e.target.value.toUpperCase())} />
          </label>
          <label>
            Prompt
            <textarea rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
          </label>
          <button className="btn primary" disabled={!canRun}>
            {running ? "Analyzing..." : "Start Analysis"}
          </button>
        </form>
        {error ? <div className="error">{error}</div> : null}
      </section>

      <section className="card">
        <h3>Agent Panel</h3>
        <div className="agent-grid">
          {agents.length === 0 && !running && (
            <p className="muted" style={{ gridColumn: "1 / -1" }}>Start an analysis to see agents in action.</p>
          )}
          {agents.map((agent) => (
            <div
              key={agent.agent}
              className={`agent-card ${agent.status === "running" ? "agent-pulse" : ""} ${agent.status === "done" ? "agent-done" : ""}`}
            >
              <div className="agent-header">
                <span className="agent-icon">{agent.icon}</span>
                <strong>{agent.label}</strong>
                <span className="agent-badge">
                  {agent.status === "running" ? "●" : agent.status === "done" ? "✓" : "○"}
                </span>
              </div>
              <div className="agent-content">{agent.content || (agent.status === "running" ? "Working..." : "")}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>Final Report</h3>
        <pre className="output">{report || "Waiting for analysis to complete..."}</pre>
        {recommendation && (
          <>
            <h4>Recommendation</h4>
            <p>{recommendation}</p>
          </>
        )}
      </section>

      {guardCheck && (
        <section className="card">
          <h3>
            🛡️ Guard Agent Verification
            <span className={`guard-badge ${guardCheck.is_valid ? "guard-valid" : "guard-invalid"}`}>
              {guardCheck.is_valid ? "PASS" : "FAIL"}
            </span>
          </h3>
          <div className="guard-grid">
            <div className="guard-stat">
              <span className="guard-label">Confidence</span>
              <span className={`guard-score ${guardCheck.confidence_score >= 80 ? "score-high" : guardCheck.confidence_score >= 60 ? "score-mid" : "score-low"}`}>
                {guardCheck.confidence_score}/100
              </span>
            </div>
            <div className="guard-stat">
              <span className="guard-label">Valid</span>
              <span>{guardCheck.is_valid ? "Yes" : "No"}</span>
            </div>
          </div>
          {guardCheck.issues.length > 0 && (
            <div className="guard-section">
              <h4>Issues Found ({guardCheck.issues.length})</h4>
              <ul>
                {guardCheck.issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {guardCheck.corrections.length > 0 && (
            <div className="guard-section">
              <h4>Corrections ({guardCheck.corrections.length})</h4>
              <ul>
                {guardCheck.corrections.map((corr, i) => (
                  <li key={i}>{corr}</li>
                ))}
              </ul>
            </div>
          )}
          {guardCheck.sources.length > 0 && (
            <div className="guard-section">
              <h4>Sources ({guardCheck.sources.length})</h4>
              <ul className="guard-sources">
                {guardCheck.sources.map((src, i) => (
                  <li key={i}>{src}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="guard-section">
            <h4>Reasoning</h4>
            <p className="guard-reasoning">{guardCheck.final_reasoning}</p>
          </div>
        </section>
      )}
    </div>
  );
}
