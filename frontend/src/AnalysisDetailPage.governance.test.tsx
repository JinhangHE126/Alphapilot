import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalysisDetailPage from "./pages/AnalysisDetailPage";
import { I18nProvider } from "./i18n";

const getHistoryDetail = vi.fn();
const getAnalysisAudit = vi.fn();
const submitAnalysisForReview = vi.fn();
const approveAnalysis = vi.fn();
const rejectAnalysis = vi.fn();
const requestAnalysisRevision = vi.fn();
const publishAnalysis = vi.fn();
const downloadAnalysisAudit = vi.fn();
const deleteHistory = vi.fn();

vi.mock("./services/api", () => ({
  getHistoryDetail: (...args: unknown[]) => getHistoryDetail(...args),
  getAnalysisAudit: (...args: unknown[]) => getAnalysisAudit(...args),
  submitAnalysisForReview: (...args: unknown[]) => submitAnalysisForReview(...args),
  approveAnalysis: (...args: unknown[]) => approveAnalysis(...args),
  rejectAnalysis: (...args: unknown[]) => rejectAnalysis(...args),
  requestAnalysisRevision: (...args: unknown[]) => requestAnalysisRevision(...args),
  publishAnalysis: (...args: unknown[]) => publishAnalysis(...args),
  downloadAnalysisAudit: (...args: unknown[]) => downloadAnalysisAudit(...args),
  deleteHistory: (...args: unknown[]) => deleteHistory(...args),
}));

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={["/history/42"]}>
      <I18nProvider>
        <Routes>
          <Route path="/history/:id" element={<AnalysisDetailPage />} />
        </Routes>
      </I18nProvider>
    </MemoryRouter>,
  );
}

describe("AnalysisDetailPage governance card", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("alphapilot-locale", "en");
    getHistoryDetail.mockResolvedValue({
      stock_symbol: "AAPL",
      analysis_type: "analyze",
      final_score: 88,
      status: "completed",
      recommendation: "Hold",
      report: "AAPL is stable [doc:1].",
      citations: null,
      events: [],
    });
    getAnalysisAudit.mockResolvedValue({
      approval_status: "pending_review",
      publication_status: "not_published",
      kill_switch_status: "enabled",
      guard_result: { is_valid: true },
      citation_validation: { claim_ok: true },
      disclaimer: "This report is AI-assisted research material.",
    });
    rejectAnalysis.mockResolvedValue({});
  });

  it("shows governance review actions for pending review", async () => {
    renderDetail();

    expect(await screen.findByText("Governance Review")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request revision" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download audit JSON" })).toBeInTheDocument();
    expect(screen.getByText(/AI-assisted research material/i)).toBeInTheDocument();
  });

  it("blocks reject without review comments", async () => {
    const user = userEvent.setup();
    renderDetail();

    await screen.findByText("Governance Review");
    await user.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() => {
      expect(screen.getByText("A review comment is required for this action.")).toBeInTheDocument();
    });
    expect(rejectAnalysis).not.toHaveBeenCalled();
  });
});
