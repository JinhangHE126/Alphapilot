import { Link2 } from "lucide-react";
import { useTranslation } from "../i18n";
import type { AnalysisCitations } from "../services/sse";

type CitationsPanelProps = {
  citations: AnalysisCitations | null | undefined;
  compact?: boolean;
};

export default function CitationsPanel({ citations, compact = false }: CitationsPanelProps) {
  const { t } = useTranslation();

  if (!citations) {
    return (
      <section className={compact ? "citations-panel citations-panel--compact" : "citations-panel"}>
        <div className="citations-panel-header">
          <Link2 size={16} />
          <h4>{t("citations.title")}</h4>
        </div>
        <p className="muted citations-empty">{t("citations.empty")}</p>
      </section>
    );
  }

  const snapshot = citations.evidence_snapshot ?? [];
  const markers = citations.doc_markers ?? [];
  const rows =
    snapshot.length > 0
      ? snapshot.map((item, i) => ({
          marker: markers[i] ?? "",
          chunkId: item.chunk_id,
          section: item.section ?? "",
          source: item.source ?? "",
          docId: item.doc_id ?? "",
        }))
      : (citations.chunk_ids ?? []).map((chunkId, i) => ({
          marker: markers[i] ?? "",
          chunkId,
          section: "",
          source: "",
          docId: "",
        }));

  if (rows.length === 0) {
    return (
      <section className={compact ? "citations-panel citations-panel--compact" : "citations-panel"}>
        <div className="citations-panel-header">
          <Link2 size={16} />
          <h4>{t("citations.title")}</h4>
        </div>
        <p className="muted citations-empty">{t("citations.noChunks")}</p>
      </section>
    );
  }

  return (
    <section className={compact ? "citations-panel citations-panel--compact" : "citations-panel"}>
      <div className="citations-panel-header">
        <Link2 size={16} />
        <h4>{t("citations.title")}</h4>
        <span className="citations-count">{t("citations.chunkCount", { count: rows.length })}</span>
      </div>
      <p className="citations-sub">{t("citations.subtitle")}</p>
      <div className="citations-table-wrap">
        <table className="citations-table">
          <thead>
            <tr>
              <th>{t("citations.colMarker")}</th>
              <th>{t("citations.colChunkId")}</th>
              <th>{t("citations.colSection")}</th>
              <th>{t("citations.colSource")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.chunkId}>
                <td>
                  {row.marker ? (
                    <code className="citations-marker">[{row.marker}]</code>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>
                  <code className="citations-chunk-id" title={row.docId || undefined}>
                    {row.chunkId}
                  </code>
                </td>
                <td>{row.section || "—"}</td>
                <td>{row.source || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
