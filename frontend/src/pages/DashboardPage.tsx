import { Activity, Clock, Layers, Plus, Sparkles, Target, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../App";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { useGreeting, useTranslation } from "../i18n";
import { getDashboardStats } from "../services/api";

type Stats = {
  total_analyses: number;
  unique_symbols: number;
  average_score: number;
  last_active: string | null;
};

type RecentItem = {
  id: number;
  stock_symbol: string;
  analysis_type: string;
  status: string;
  final_score: number;
  created_at: string;
};

export default function DashboardPage() {
  const { auth } = useAuth();
  const { t, dateLocale } = useTranslation();
  const greeting = useGreeting();
  const [stats, setStats] = useState<Stats | null>(null);
  const [recent, setRecent] = useState<RecentItem[]>([]);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    getDashboardStats()
      .then((data) => {
        setStats(data.stats);
        setRecent(data.recent_analyses as RecentItem[]);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("errors.loadDashboard")));
  }, [t]);

  const todayDate = useMemo(() => {
    return new Date().toLocaleDateString(dateLocale, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }, [dateLocale]);

  const todayWeekday = useMemo(() => {
    return new Date().toLocaleDateString(dateLocale, { weekday: "long" });
  }, [dateLocale]);

  return (
    <div className="page">
      <header className="header-bar">
        <div className="header-left">
          <span className="header-greeting">
            <Zap size={16} className="header-zap" />
            {greeting}，{auth.username || t("dashboard.commander")}
          </span>
          <div className="header-date-row">
            <span className="header-date">{todayDate}</span>
            <span className="header-date-sep">·</span>
            <span className="header-weekday">{todayWeekday}</span>
          </div>
        </div>
        <div className="header-actions">
          <LanguageSwitcher variant="compact" />
          <button className="btn header-btn" onClick={() => navigate("/analyze")}>
            <Plus size={18} />
            {t("dashboard.newAnalysis")}
          </button>
        </div>
      </header>

      <section className="card">
        <h2 className="page-title">{t("dashboard.overview")}</h2>
        <p className="overview-subtitle">{t("dashboard.overviewSubtitle")}</p>
        {error ? <div className="error">{error}</div> : null}
        <div className="stats">
          <div className="metric-card">
            <Activity size={28} className="metric-icon" />
            <div className="metric-value">{stats?.total_analyses ?? "-"}</div>
            <div className="metric-label">{t("dashboard.totalAnalyses")}</div>
            <div className="metric-sub">{t("dashboard.totalAnalysesSub")}</div>
          </div>
          <div className="metric-card">
            <Layers size={28} className="metric-icon" />
            <div className="metric-value">{stats?.unique_symbols ?? "-"}</div>
            <div className="metric-label">{t("dashboard.symbolsAnalyzed")}</div>
            <div className="metric-sub">{t("dashboard.symbolsAnalyzedSub")}</div>
          </div>
          <div className="metric-card">
            <Target size={28} className="metric-icon" />
            <div className="metric-value">{stats?.average_score ?? "-"}</div>
            <div className="metric-label">{t("dashboard.avgConfidence")}</div>
            <div className="metric-sub">{t("dashboard.avgConfidenceSub")}</div>
          </div>
          <div className="metric-card">
            <Clock size={28} className="metric-icon" />
            <div className="metric-value">
              {stats?.last_active ? new Date(stats.last_active).toLocaleDateString(dateLocale) : "-"}
            </div>
            <div className="metric-label">{t("dashboard.lastAnalysis")}</div>
            <div className="metric-sub">{t("dashboard.lastAnalysisSub")}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3 className="card-title">{t("dashboard.recentAnalyses")}</h3>
        <div className="list">
          {recent.length === 0 ? (
            <div className="empty-state">
              <Sparkles size={48} className="empty-icon" />
              <h4>{t("dashboard.emptyTitle")}</h4>
              <p>{t("dashboard.emptyDesc")}</p>
              <button className="btn accent" onClick={() => navigate("/analyze")}>
                {t("dashboard.startFirst")}
              </button>
            </div>
          ) : (
            recent.map((item) => (
              <button
                key={item.id}
                className="list-item"
                onClick={() => navigate(`/history/${item.id}`)}
              >
                <span>
                  {item.stock_symbol} — {item.analysis_type}
                </span>
                <small>
                  {t("dashboard.listScore")}: {item.final_score} · {item.status} ·{" "}
                  {new Date(item.created_at).toLocaleString(dateLocale)}
                </small>
              </button>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
