import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
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
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard"));
  }, []);

  return (
    <div className="page">
      <section className="card">
        <h2>Overview</h2>
        <p className="muted">AlphaPilot enterprise command center.</p>
        {error ? <div className="error">{error}</div> : null}
        <div className="stats">
          <div>
            <strong>{stats?.total_analyses ?? "-"}</strong>
            <span>Total Analyses</span>
          </div>
          <div>
            <strong>{stats?.unique_symbols ?? "-"}</strong>
            <span>Unique Symbols</span>
          </div>
          <div>
            <strong>{stats?.average_score ?? "-"}</strong>
            <span>Average Score</span>
          </div>
          <div>
            <strong>{stats?.last_active ? new Date(stats.last_active).toLocaleDateString() : "-"}</strong>
            <span>Last Active</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Recent Analyses</h3>
        <div className="list">
          {recent.length === 0 ? (
            <p className="muted">No analyses yet. Start one from the Analyze tab.</p>
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
                  Score: {item.final_score} · {item.status} · {new Date(item.created_at).toLocaleString()}
                </small>
              </button>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
