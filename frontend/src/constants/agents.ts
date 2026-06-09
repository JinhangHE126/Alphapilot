import {
  BarChart3,
  Brain,
  Database,
  LineChart,
  Newspaper,
  PieChart,
  ShieldAlert,
  Sparkles,
  Target,
  TrendingUp,
  Swords,
  type LucideIcon,
} from "lucide-react";

/** Core analysis agents — always shown on Analyze page. */
export const CORE_AGENT_IDS = [
  "market_data_expert",
  "fundamental_expert",
  "news_sentiment_expert",
  "strategy_expert",
  "risk_expert",
  "guard_agent",
] as const;

/** Extra agents — shown only when they appear in the SSE stream. */
export const ENHANCEMENT_AGENT_IDS = [
  "recommendation_agent",
  "portfolio_agent",
  "backtesting_agent",
  "debate_stage",
] as const;

/** Infrastructure nodes — compact pipeline bar. */
export const SYSTEM_NODE_IDS = ["evidence_packet_builder", "orchestrator"] as const;

/** @deprecated Use CORE_AGENT_IDS */
export const STREAM_AGENT_IDS = CORE_AGENT_IDS;

export type CoreAgentId = (typeof CORE_AGENT_IDS)[number];
export type EnhancementAgentId = (typeof ENHANCEMENT_AGENT_IDS)[number];
export type SystemNodeId = (typeof SYSTEM_NODE_IDS)[number];
export type WorkflowNodeId = CoreAgentId | EnhancementAgentId | SystemNodeId;

/** @deprecated Use CoreAgentId */
export type StreamAgentId = CoreAgentId;

export const ALL_WORKFLOW_NODE_IDS = [
  ...SYSTEM_NODE_IDS,
  ...CORE_AGENT_IDS,
  ...ENHANCEMENT_AGENT_IDS,
] as const;

export const AGENT_VISUAL: Record<
  WorkflowNodeId,
  { icon: string; lucide: LucideIcon; color: string }
> = {
  evidence_packet_builder: { icon: "📦", lucide: Database, color: "#94a3b8" },
  orchestrator: { icon: "🧠", lucide: Brain, color: "#64748b" },
  market_data_expert: { icon: "📈", lucide: TrendingUp, color: "#60a5fa" },
  fundamental_expert: { icon: "📊", lucide: BarChart3, color: "#4ade80" },
  news_sentiment_expert: { icon: "📰", lucide: Newspaper, color: "#c084fc" },
  strategy_expert: { icon: "🎯", lucide: Target, color: "#22d3ee" },
  risk_expert: { icon: "🛡️", lucide: ShieldAlert, color: "#f87171" },
  guard_agent: { icon: "🛡️", lucide: ShieldAlert, color: "#a78bfa" },
  recommendation_agent: { icon: "⭐", lucide: Sparkles, color: "#fbbf24" },
  portfolio_agent: { icon: "💼", lucide: PieChart, color: "#34d399" },
  backtesting_agent: { icon: "📉", lucide: LineChart, color: "#f472b6" },
  debate_stage: { icon: "⚔️", lucide: Swords, color: "#fb923c" },
};

export function isSystemNode(id: string): id is SystemNodeId {
  return (SYSTEM_NODE_IDS as readonly string[]).includes(id);
}

export function isWorkflowNodeId(id: string): id is WorkflowNodeId {
  return id in AGENT_VISUAL;
}

const REPORT_PLACEHOLDERS = new Set(["分析完成", "分析完成。", "Analysis complete"]);

export function isPlaceholderReport(report: string): boolean {
  return !report.trim() || REPORT_PLACEHOLDERS.has(report.trim());
}

const REPORT_EXCLUDE = new Set([
  ...SYSTEM_NODE_IDS,
  "orchestrator",
  "guard_agent",
  "guard",
]);

const REPORT_ORDER = [
  "market_data_expert",
  "fundamental_expert",
  "news_sentiment_expert",
  "debate_stage",
  "strategy_expert",
  "risk_expert",
  "portfolio_agent",
  "backtesting_agent",
  "recommendation_agent",
  "guard_agent",
] as const;

export function buildReportFromAgents(
  agents: { agent: string; label: string; content: string }[],
): string {
  const deduped = agents.filter(
    (a, i, arr) => arr.findIndex((x) => x.agent === a.agent) === i,
  );
  const byAgent = new Map(
    deduped
      .filter((a) => !REPORT_EXCLUDE.has(a.agent) && a.content.trim())
      .map((a) => [a.agent, a]),
  );

  const ordered: typeof agents = [];
  for (const id of REPORT_ORDER) {
    const item = byAgent.get(id);
    if (item) {
      ordered.push(item);
      byAgent.delete(id);
    }
  }
  for (const item of byAgent.values()) {
    ordered.push(item);
  }

  return ordered.map((a) => `### ${a.label}\n\n${a.content}`).join("\n\n---\n\n");
}
