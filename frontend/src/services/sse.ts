import { authHeader } from "./api";

export type GuardCheck = {
  is_valid: boolean;
  confidence_score: number;
  issues: string[];
  corrections: string[];
  sources: string[];
  final_reasoning: string;
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

export type EvidencePacketData = {
  symbol: string;
  facts: EvidenceFact[];
  evidence_score: number;
  allowed_output_level: string;
  chart_data: ChartPoint[];
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
};

export type StreamEvent =
  | { event: "analysis_start"; data: { session_id: string; thread_id: string; stock_symbol: string; analysis_type: string } }
  | { event: "evidence_packet"; data: EvidencePacketData }
  | { event: "agent_start"; data: { agent: string; label: string; icon: string } }
  | { event: "agent_output"; data: { agent: string; content: string } }
  | { event: "agent_done"; data: { agent: string } }
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
