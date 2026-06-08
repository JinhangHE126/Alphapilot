import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import MarkdownContent from "../components/MarkdownContent";
import { useTranslation } from "../i18n";
import { deleteHistory, getHistoryDetail } from "../services/api";

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

  useEffect(() => {
    if (!id) return;
    getHistoryDetail(Number(id))
      .then((data) => {
        setRecord(data);
        setEvents((data.events as EventItem[]) || []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("errors.loadDetail")));
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

  if (!record) {
    return (
      <div className="page">
        <section className="card">
          <p className="muted">{error || t("common.loading")}</p>
        </section>
      </div>
    );
  }

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
