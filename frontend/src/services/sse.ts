import { authHeader } from "./api";

export type GuardCheckItem = {
  passed: boolean;
  detail: string;
};

export type GuardChecks = {
  data_coverage: GuardCheckItem;
  symbol_match: GuardCheckItem;
  unsupported_claim: GuardCheckItem;
};

export type GuardCheck = {
  is_valid: boolean;
  confidence_score: number;
  issues: string[];
  corrections: string[];
  sources: string[];
  final_reasoning: string;
  checks?: GuardChecks;
  risk_warnings?: string[];
};

export type EvidenceFact = {
  field: string;
  value: number | string;
  unit: string;
  period: string;
  source: string;
  as_of_date?: string;
  confidence?: number;
};

export type ChartPoint = {
  t: string;
  o?: number;
  h?: number;
  l?: number;
  c: number;
  v?: number;
};

export type DocumentEvidenceItem = {
  source: string;
  doc_id: string;
  doc_type: string;
  section: string;
  publish_date: string;
  report_period: string;
  page: string;
};

export type EvidencePacketData = {
  symbol: string;
  facts: EvidenceFact[];
  evidence_score: number;
  allowed_output_level: string;
  chart_data: ChartPoint[];
  document_evidence: DocumentEvidenceItem[];
};

export type TargetPriceData = {
  target_price_low: number | null;
  target_price_mid: number | null;
  target_price_high: number | null;
  valuation_low?: number | null;
  valuation_mid?: number | null;
  valuation_high?: number | null;
  upside_pct: number | null;
  downside_pct: number | null;
  consensus_summary?: string;
  source?: string;
};

export type RiskLevelData = {
  overall_risk_score: number;
  volatility_risk?: string;
  macro_risk?: string;
  stop_loss_suggestion?: number | string;
  position_suggestion?: string;
  risk_reasoning?: string;
  key_risks?: string[];
};

function extractBalancedJson(text: string, which: "first" | "last" = "last"): string | null {
  const starts: number[] = [];
  for (let i = 0; i < text.length; i++) {
    if (text[i] === "{") starts.push(i);
  }
  const order = which === "first" ? starts : [...starts].reverse();
  for (const start of order) {
    let depth = 0;
    for (let j = start; j < text.length; j++) {
      if (text[j] === "{") depth++;
      else if (text[j] === "}") depth--;
      if (depth === 0) return text.slice(start, j + 1);
    }
  }
  return null;
}

/** Parse risk_expert JSON / markdown output into RiskLevelData. */
export function parseRiskLevelFromContent(content: string): RiskLevelData | null {
  const trimmed = content.trim();
  if (!trimmed) return null;

  const jsonText = trimmed.startsWith("{")
    ? trimmed
    : extractBalancedJson(trimmed, "last");
  if (!jsonText) return null;

  try {
    const obj = JSON.parse(jsonText) as Record<string, unknown>;
    const overall = obj.overall_risk_score ?? obj.risk_score;
    if (overall === undefined || overall === null) return null;

    const score = Math.round(Number(overall));
    if (!Number.isFinite(score)) return null;
    if (score === 0 && String(obj.volatility_risk ?? "").toUpperCase() === "N/A") return null;

    const keyRisks = Array.isArray(obj.key_risks)
      ? obj.key_risks.map((r) => String(r)).filter(Boolean)
      : [];

    return {
      overall_risk_score: Math.min(100, Math.max(0, score)),
      volatility_risk: typeof obj.volatility_risk === "string" ? obj.volatility_risk : undefined,
      macro_risk: typeof obj.macro_risk === "string" ? obj.macro_risk : undefined,
      stop_loss_suggestion: obj.stop_loss_suggestion as number | string | undefined,
      position_suggestion: typeof obj.position_suggestion === "string" ? obj.position_suggestion : undefined,
      risk_reasoning: typeof obj.risk_reasoning === "string" ? obj.risk_reasoning : undefined,
      key_risks: keyRisks,
    };
  } catch {
    return null;
  }
}

/** Estimate risk score from market facts when risk agent score is unavailable. */
export function estimateRiskScoreFromFacts(volatility?: number, maxDrawdown?: number): number | undefined {
  if (volatility === undefined) return undefined;
  let score = Math.round(volatility * 2);
  if (maxDrawdown !== undefined) {
    score = Math.round(score * 0.55 + maxDrawdown * 2.2);
  }
  return Math.min(100, Math.max(5, score));
}

export function riskLevelFromScore(score: number): "low" | "medium" | "high" {
  if (score <= 30) return "low";
  if (score <= 60) return "medium";
  return "high";
}

export type DebateClaim = {
  text: string;
  confidence: number;
  sources: string[];
  supporting_fields: string[];
};

export type DebateStructuredData = {
  stance_strength: number;
  summary: string;
  claims: DebateClaim[];
};

export type StreamEvent =
  | { event: "analysis_start"; data: { session_id: string; thread_id: string; stock_symbol: string; analysis_type: string } }
  | { event: "evidence_packet"; data: EvidencePacketData }
  | { event: "agent_start"; data: { agent: string; label: string; icon: string } }
  | { event: "agent_output"; data: { agent: string; content: string } }
  | { event: "agent_core_conclusion"; data: { agent: string; core_conclusion: string; conclusion_sentiment: "positive" | "negative" | "neutral"; confidence_score?: number } }
  | { event: "agent_done"; data: { agent: string; duration_ms: number } }
  | { event: "agent_error"; data: { agent: string; label: string; icon: string; message: string; duration_ms: number } }
  | { event: "agent_skipped"; data: { agent: string; label: string; icon: string } }
  | { event: "analysis_complete"; data: { final_report: string; recommendation?: string; guard_check?: GuardCheck; target_price?: TargetPriceData | null; risk_level?: RiskLevelData | null } }
  | { event: "target_price"; data: TargetPriceData }
  | { event: "risk_level"; data: RiskLevelData }
  | { event: "error"; data: { detail: string } };

function encodeBody(body: Record<string, unknown>) {
  return JSON.stringify(body);
}

export async function streamAnalyze(
  payload: { session_id: string; message: string; stock_symbol: string; language?: string },
  onEvent: (event: StreamEvent) => void,
) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const auth = authHeader();
  if (auth.Authorization) {
    headers.Authorization = auth.Authorization;
  }

  const response = await fetch("/api/analyze/stream", {
    method: "POST",
    headers,
    body: encodeBody(payload),
  });
  if (!response.ok || !response.body) {
    throw new Error("Unable to open stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const eventLine = chunk.split("\n").find((line) => line.startsWith("event: "));
      const dataLine = chunk.split("\n").find((line) => line.startsWith("data: "));
      if (!eventLine || !dataLine) continue;

      const eventName = eventLine.replace("event: ", "").trim();
      const rawData = dataLine.replace("data: ", "").trim();
      try {
        const parsed = JSON.parse(rawData) as StreamEvent["data"];
        onEvent({ event: eventName as StreamEvent["event"], data: parsed } as StreamEvent);
      } catch {
        onEvent({ event: "error", data: { detail: "Malformed stream payload" } });
      }
    }
  }
}
