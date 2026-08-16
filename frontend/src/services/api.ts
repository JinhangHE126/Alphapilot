const API_BASE = "/api";

type JsonValue = Record<string, unknown>;

interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

function getToken(): string | null {
  return localStorage.getItem("alphapilot_token");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers ?? {});
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const payload = (await response.json()) as ApiResponse<T> & { detail?: string };
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : payload.message || "Request failed";
    throw new Error(detail);
  }
  return payload.data as T;
}

export async function register(username: string, password: string, displayName?: string) {
  return request<{ user_id: number; username: string; access_token: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password, display_name: displayName }),
  });
}

export async function login(username: string, password: string) {
  return request<{ access_token: string; token_type: string; user_id: number; username: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function refreshToken() {
  return request<{ access_token: string }>("/auth/refresh", { method: "POST" });
}

export async function getMe() {
  return request<{ id: number; username: string }>("/auth/me");
}

export async function createSession(title: string) {
  return request<{ id: string; title: string }>("/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function listSessions() {
  return request<Array<{ id: string; title: string; updated_at: string }>>("/sessions");
}

export async function getSessionMessages(sessionId: string) {
  return request<{
    session: { id: string; title: string };
    messages: Array<{ id: number; role: string; content: string; created_at: string }>;
  }>(`/sessions/${sessionId}/messages`);
}

export async function analyze(sessionId: string, message: string, stockSymbol: string) {
  return request<{ session_id: string; report: string; recommendation?: string }>("/analyze", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, message, stock_symbol: stockSymbol }),
  });
}

export async function getDashboardStats() {
  return request<{
    stats: { total_analyses: number; unique_symbols: number; average_score: number; last_active: string | null };
    recent_analyses: Array<Record<string, unknown>>;
  }>("/dashboard/stats");
}

/** 上传文档 PDF → 向量库 */
export async function uploadDocument(
  file: File,
  symbol: string,
  docType: string = "annual_report",
  source: string = "user_uploaded",
  publishDate?: string,
  reportPeriod?: string,
  language?: string,
  consentAt?: string,
) {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("symbol", symbol);
  formData.append("doc_type", docType);
  formData.append("source", source);
  if (publishDate) formData.append("publish_date", publishDate);
  if (reportPeriod) formData.append("report_period", reportPeriod);
  if (language) formData.append("language", language);
  if (consentAt) formData.append("consent_at", consentAt);

  const response = await fetch(`${API_BASE}/upload/document`, {
    method: "POST",
    headers,
    body: formData,
  });
  const payload = (await response.json()) as ApiResponse<{ doc_id: string; chunks: number; symbol: string; doc_type: string; message: string }> & { detail?: string };
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : payload.message || "Upload failed";
    throw new Error(detail);
  }
  return payload.data;
}

export async function getHistory(page = 1, pageSize = 20, stockSymbol?: string) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (stockSymbol) params.set("stock_symbol", stockSymbol);
  return request<{
    items: Array<Record<string, unknown>>;
    total: number;
    page: number;
    page_size: number;
  }>(`/history?${params}`);
}

export async function getHistoryDetail(analysisId: number) {
  return request<Record<string, unknown> & { events: Array<Record<string, unknown>> }>(
    `/history/${analysisId}`,
  );
}

export async function deleteHistory(analysisId: number) {
  return request<null>(`/history/${analysisId}`, { method: "DELETE" });
}

export type AuditRecord = {
  approval_status: string;
  publication_status: string;
  human_reviewer?: string | null;
  review_comments?: string | null;
  approval_timestamp?: string | null;
  kill_switch_status?: string | null;
  guard_result?: { is_valid?: boolean } | null;
  citation_validation?: { ok?: boolean; claim_ok?: boolean } | null;
  disclaimer?: string | null;
  disclaimer_version?: string | null;
};

export async function getAnalysisAudit(analysisId: number) {
  return request<AuditRecord>(`/analyses/${analysisId}/audit`);
}

export async function submitAnalysisForReview(analysisId: number) {
  return request<AuditRecord>(`/analyses/${analysisId}/submit-review`, { method: "POST" });
}

export async function approveAnalysis(analysisId: number, comments?: string) {
  return request<AuditRecord>(`/analyses/${analysisId}/approve`, {
    method: "POST",
    body: JSON.stringify({ comments: comments || null }),
  });
}

export async function rejectAnalysis(analysisId: number, comments: string) {
  return request<AuditRecord>(`/analyses/${analysisId}/reject`, {
    method: "POST",
    body: JSON.stringify({ comments }),
  });
}

export async function requestAnalysisRevision(analysisId: number, comments: string) {
  return request<AuditRecord>(`/analyses/${analysisId}/request-revision`, {
    method: "POST",
    body: JSON.stringify({ comments }),
  });
}

export async function publishAnalysis(analysisId: number) {
  return request<AuditRecord>(`/analyses/${analysisId}/publish`, { method: "POST" });
}

export async function downloadAnalysisAudit(analysisId: number) {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE}/analyses/${analysisId}/audit/export`, { headers });
  if (!response.ok) {
    const payload = (await response.json()) as { detail?: string; message?: string };
    throw new Error(payload.detail || payload.message || "Audit export failed");
  }

  const downloadUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = `analysis-${analysisId}-audit.json`;
  link.click();
  URL.revokeObjectURL(downloadUrl);
}

export async function saveToken(token: string) {
  localStorage.setItem("alphapilot_token", token);
}

export async function getProfile() {
  return request<Record<string, unknown>>("/profile");
}

export async function updateProfile(profile: Record<string, unknown>) {
  return request<Record<string, unknown>>("/profile", { method: "PUT", body: JSON.stringify(profile) });
}

export function clearToken() {
  localStorage.removeItem("alphapilot_token");
}

export function hasToken() {
  return Boolean(getToken());
}

export function authHeader() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
