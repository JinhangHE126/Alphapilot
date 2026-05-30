import { authHeader } from "./api";

export type GuardCheck = {
  is_valid: boolean;
  confidence_score: number;
  issues: string[];
  corrections: string[];
  sources: string[];
  final_reasoning: string;
};

export type StreamEvent =
  | { event: "analysis_start"; data: { session_id: string; thread_id: string; stock_symbol: string; analysis_type: string } }
  | { event: "agent_start"; data: { agent: string; label: string; icon: string } }
  | { event: "agent_output"; data: { agent: string; content: string } }
  | { event: "agent_done"; data: { agent: string } }
  | { event: "analysis_complete"; data: { final_report: string; recommendation?: string; guard_check?: GuardCheck } }
  | { event: "error"; data: { detail: string } };

function encodeBody(body: Record<string, unknown>) {
  return JSON.stringify(body);
}

export async function streamAnalyze(
  payload: { session_id: string; message: string; stock_symbol: string },
  onEvent: (event: StreamEvent) => void,
) {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...authHeader(),
  };

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
