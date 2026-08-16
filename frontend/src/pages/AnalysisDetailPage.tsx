import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import CitationsPanel from "../components/CitationsPanel";
import MarkdownContent from "../components/MarkdownContent";
import { useTranslation } from "../i18n";
import {
  approveAnalysis,
  deleteHistory,
  downloadAnalysisAudit,
  getAnalysisAudit,
  getHistoryDetail,
  publishAnalysis,
  rejectAnalysis,
  requestAnalysisRevision,
  submitAnalysisForReview,
  type AuditRecord,
} from "../services/api";
import type { AnalysisCitations } from "../services/sse";

type EventItem = {
  id: number;
  seq_num: number;
  agent_name: string;
  event_type: string;
  content: string;
  created_at: string;
};

export default function AnalysisDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [record, setRecord] = useState<Record<string, unknown> | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [error, setError] = useState("");
  const [audit, setAudit] = useState<AuditRecord | null>(null);
  const [governanceError, setGovernanceError] = useState("");
  const [reviewComments, setReviewComments] = useState("");
  const [isActionPending, setIsActionPending] = useState(false);

  useEffect(() => {
    if (!id) return;
    getHistoryDetail(Number(id))
      .then((data) => {
        setRecord(data);
        setEvents((data.events as EventItem[]) || []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("errors.loadDetail")));
    getAnalysisAudit(Number(id))
      .then(setAudit)
      .catch((err) => setGovernanceError(err instanceof Error ? err.message : t("errors.loadGovernance")));
  }, [id, t]);

  async function handleDelete() {
    if (!id) return;
    try {
      await deleteHistory(Number(id));
      navigate("/history");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("errors.deleteFailed"));
    }
  }

  async function handleGovernanceAction(
    action: "submit" | "approve" | "reject" | "revision" | "publish" | "download",
  ) {
    if (!id) return;
    if ((action === "reject" || action === "revision") && !reviewComments.trim()) {
      setGovernanceError(t("detail.reviewCommentRequired"));
      return;
    }

    setGovernanceError("");
    setIsActionPending(true);
    try {
      const analysisId = Number(id);
      if (action === "submit") setAudit(await submitAnalysisForReview(analysisId));
      if (action === "approve") setAudit(await approveAnalysis(analysisId, reviewComments.trim()));
      if (action === "reject") setAudit(await rejectAnalysis(analysisId, reviewComments.trim()));
      if (action === "revision") setAudit(await requestAnalysisRevision(analysisId, reviewComments.trim()));
      if (action === "publish") setAudit(await publishAnalysis(analysisId));
      if (action === "download") await downloadAnalysisAudit(analysisId);
      if (action !== "download") setReviewComments("");
    } catch (err) {
      setGovernanceError(err instanceof Error ? err.message : t("errors.governanceActionFailed"));
    } finally {
      setIsActionPending(false);
    }
  }

  if (!record) {
    return (
      <div className="page">
        <section className="card">
          <p className="muted">{error || t("common.loading")}</p>
        </section>
      </div>
    );
  }

  const citations = (record.citations as AnalysisCitations | null | undefined) ?? null;

  return (
    <div className="page">
      <section className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>
            {record.stock_symbol as string} — {record.analysis_type as string}
          </h2>
          <div style={{ display: "flex", gap: "0.4rem" }}>
            <button className="btn ghost" onClick={() => navigate("/history")}>
              {t("common.back")}
            </button>
            <button className="btn ghost" onClick={handleDelete}>
              {t("common.delete")}
            </button>
          </div>
        </div>
        <div className="stats" style={{ marginTop: "0.5rem" }}>
          <div>
            <strong>{record.final_score as number}</strong>
            <span>{t("detail.finalScore")}</span>
          </div>
          <div>
            <strong>{record.status as string}</strong>
            <span>{t("detail.status")}</span>
          </div>
          <div>
            <strong>{(record.recommendation as string) || "-"}</strong>
            <span>{t("detail.recommendation")}</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>{t("detail.report")}</h3>
        <div className="output">
          <MarkdownContent
            content={(record.report as string) || ""}
            emptyFallback={t("detail.noReport")}
          />
        </div>
      </section>

      <section className="card citations-card">
        <CitationsPanel citations={citations} />
      </section>

      <section className="card governance-card">
        <div className="governance-card-header">
          <div>
            <h3>{t("detail.governanceTitle")}</h3>
            <p className="muted">{t("detail.governanceSubtitle")}</p>
          </div>
          {audit && (
            <span className={`governance-status status-${audit.approval_status}`}>
              {t(`detail.approvalStatus.${audit.approval_status}`)}
            </span>
          )}
        </div>

        {governanceError && <p className="error">{governanceError}</p>}
        {!audit ? (
          <p className="muted">{t("detail.noAudit")}</p>
        ) : (
          <>
            <dl className="governance-summary">
              <div>
                <dt>{t("detail.publicationStatus")}</dt>
                <dd>{t(`detail.publicationStatusValue.${audit.publication_status}`)}</dd>
              </div>
              <div>
                <dt>{t("detail.guardStatus")}</dt>
                <dd>{audit.guard_result?.is_valid ? t("detail.passed") : t("detail.notPassed")}</dd>
              </div>
              <div>
                <dt>{t("detail.citationStatus")}</dt>
                <dd>{audit.citation_validation?.claim_ok ? t("detail.passed") : t("detail.notPassed")}</dd>
              </div>
              <div>
                <dt>{t("detail.killSwitchStatus")}</dt>
                <dd>{audit.kill_switch_status || "-"}</dd>
              </div>
              {audit.human_reviewer && (
                <div>
                  <dt>{t("detail.reviewer")}</dt>
                  <dd>{audit.human_reviewer}</dd>
                </div>
              )}
              {audit.approval_timestamp && (
                <div>
                  <dt>{t("detail.reviewedAt")}</dt>
                  <dd>{new Date(audit.approval_timestamp).toLocaleString()}</dd>
                </div>
              )}
            </dl>

            {audit.review_comments && (
              <p className="governance-comments">
                <strong>{t("detail.reviewComments")}:</strong> {audit.review_comments}
              </p>
            )}

            {audit.approval_status === "pending_review" && (
              <label className="governance-comment-input">
                {t("detail.reviewComment")}
                <textarea
                  value={reviewComments}
                  onChange={(event) => setReviewComments(event.target.value)}
                  placeholder={t("detail.reviewCommentPlaceholder")}
                  rows={3}
                />
              </label>
            )}

            <div className="governance-actions">
              {(audit.approval_status === "draft" || audit.approval_status === "revision_requested") && (
                <button className="btn primary" disabled={isActionPending} onClick={() => handleGovernanceAction("submit")}>
                  {t("detail.submitReview")}
                </button>
              )}
              {audit.approval_status === "pending_review" && (
                <>
                  <button className="btn primary" disabled={isActionPending} onClick={() => handleGovernanceAction("approve")}>
                    {t("detail.approve")}
                  </button>
                  <button className="btn ghost" disabled={isActionPending} onClick={() => handleGovernanceAction("revision")}>
                    {t("detail.requestRevision")}
                  </button>
                  <button className="btn ghost" disabled={isActionPending} onClick={() => handleGovernanceAction("reject")}>
                    {t("detail.reject")}
                  </button>
                </>
              )}
              {audit.approval_status === "approved" && audit.publication_status !== "published" && (
                <button className="btn primary" disabled={isActionPending} onClick={() => handleGovernanceAction("publish")}>
                  {t("detail.publish")}
                </button>
              )}
              <button className="btn ghost" disabled={isActionPending} onClick={() => handleGovernanceAction("download")}>
                {t("detail.downloadAudit")}
              </button>
            </div>
          </>
        )}
        <p className="governance-disclaimer">
          {audit?.disclaimer || t("detail.disclaimer")}
        </p>
      </section>

      <section className="card">
        <h3>{t("detail.eventTimeline")}</h3>
        <div className="timeline">
          {events.length === 0 ? (
            <p className="muted">{t("detail.noEvents")}</p>
          ) : (
            events.map((evt) => (
              <div key={evt.id} className="timeline-item">
                <span className="timeline-seq">#{evt.seq_num}</span>
                <div>
                  <strong>{evt.agent_name}</strong>
                  <small className="muted"> — {evt.event_type}</small>
                  {evt.content && (
                    <div className="timeline-content">
                      <MarkdownContent content={evt.content} />
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
