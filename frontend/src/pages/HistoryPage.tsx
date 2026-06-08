import { ArrowRight, Calendar, Clock, Eye, Search, Sparkles, Trash2, TrendingUp, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "../i18n";
import { deleteHistory, getHistory } from "../services/api";

type HistoryItem = {
  id: number;
  stock_symbol: string;
  analysis_type: string;
  status: string;
  final_score: number;
  recommendation: string;
  created_at: string;
};

export default function HistoryPage() {
  const { t, dateLocale } = useTranslation();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [stockFilter, setStockFilter] = useState("");
  const [error, setError] = useState("");
  const pageSize = 20;
  const navigate = useNavigate();

  async function load(pageNum: number, filter: string) {
    try {
      const data = await getHistory(pageNum, pageSize, filter || undefined);
      setItems(data.items as HistoryItem[]);
      setTotal(data.total);
      setPage(data.page);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("errors.loadHistory"));
    }
  }

  useEffect(() => {
    load(1, stockFilter);
  }, [stockFilter, t]);

  const totalPages = Math.ceil(total / pageSize);

  async function handleDelete(id: number) {
    try {
      await deleteHistory(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
      setTotal((prev) => prev - 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("errors.deleteFailed"));
    }
  }

  function formatDate(iso: string) {
    const d = new Date(iso);
    return d.toLocaleDateString(dateLocale, { month: "short", day: "numeric", year: "numeric" });
  }

  function formatTime(iso: string) {
    const d = new Date(iso);
    return d.toLocaleTimeString(dateLocale, { hour: "2-digit", minute: "2-digit" });
  }

  const avgScore =
    items.length > 0
      ? (items.reduce((sum, i) => sum + (i.final_score || 0), 0) / items.length).toFixed(0)
      : null;

  return (
    <div className="page">
      <header className="history-header">
        <div className="history-header-left">
          <span className="history-header-title">
            <Clock size={18} className="history-header-icon" />
            {t("history.title")}
          </span>
          <span className="history-header-sub">
            {total > 0 && avgScore
              ? t("history.subtitleWithScore", { count: total, avg: avgScore })
              : t("history.subtitleEmpty")}
          </span>
        </div>
        <div className="history-header-right">
          <div className="history-search">
            <Search size={14} className="history-search-icon" />
            <input
              className="history-search-input"
              placeholder={t("history.filterPlaceholder")}
              value={stockFilter}
              onChange={(e) => setStockFilter(e.target.value.toUpperCase())}
            />
            {stockFilter && (
              <button className="history-search-clear" onClick={() => setStockFilter("")}>
                <X size={14} />
              </button>
            )}
          </div>
          <button className="btn header-btn" onClick={() => navigate("/analyze")}>
            <TrendingUp size={16} />
            {t("history.newAnalysis")}
          </button>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}

      {items.length === 0 ? (
        <section className="history-empty-section">
          <div className="history-empty-icon-wrap">
            <Sparkles size={44} className="history-empty-icon" />
          </div>
          <h3 className="history-empty-title">{t("history.emptyTitle")}</h3>
          <p className="history-empty-desc">{t("history.emptyDesc")}</p>
          <button className="btn accent" onClick={() => navigate("/analyze")}>
            {t("history.startFirst")}
            <ArrowRight size={16} />
          </button>
        </section>
      ) : (
        <section className="card">
          <div className="history-list">
            {items.map((item) => (
              <div key={item.id} className="history-item" onClick={() => navigate(`/history/${item.id}`)}>
                <div className="history-item-left">
                  <div className="history-item-symbol">{item.stock_symbol}</div>
                  <div className="history-item-meta">
                    <span className="history-item-type">{item.analysis_type}</span>
                    <span className="history-item-date">
                      <Calendar size={12} />
                      {formatDate(item.created_at)}
                    </span>
                    <span className="history-item-time">{formatTime(item.created_at)}</span>
                  </div>
                </div>
                <div className="history-item-right">
                  <div className={`history-score ${item.final_score >= 70 ? "score-high" : item.final_score >= 50 ? "score-mid" : "score-low"}`}>
                    <span className="history-score-val">{item.final_score}</span>
                    <span className="history-score-label">/100</span>
                  </div>
                  <span className={`history-status ${item.status === "completed" ? "done" : "running"}`}>
                    {item.status === "completed" ? t("history.statusDone") : item.status}
                  </span>
                  <div className="history-item-actions">
                    <button
                      className="history-action-btn"
                      onClick={(e) => { e.stopPropagation(); navigate(`/history/${item.id}`); }}
                      title={t("history.viewReport")}
                    >
                      <Eye size={15} />
                      <span>{t("common.view")}</span>
                    </button>
                    <button
                      className="history-action-btn history-action-delete"
                      onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }}
                      title={t("common.delete")}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="pagination">
              <button className="btn ghost" disabled={page <= 1} onClick={() => load(page - 1, stockFilter)}>
                {t("common.prev")}
              </button>
              <span>{t("common.pageOf", { page, total: totalPages })}</span>
              <button className="btn ghost" disabled={page >= totalPages} onClick={() => load(page + 1, stockFilter)}>
                {t("common.next")}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
