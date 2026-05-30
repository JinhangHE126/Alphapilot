import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
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
      setError(err instanceof Error ? err.message : "Failed to load history");
    }
  }

  useEffect(() => {
    load(1, stockFilter);
  }, [stockFilter]);

  const totalPages = Math.ceil(total / pageSize);

  async function handleDelete(id: number) {
    try {
      await deleteHistory(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
      setTotal((prev) => prev - 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="page">
      <section className="card">
        <h2>History</h2>
        <div className="form-grid" style={{ marginBottom: "0.5rem" }}>
          <label>
            Filter by Symbol
            <input
              placeholder="e.g. TSLA"
              value={stockFilter}
              onChange={(e) => setStockFilter(e.target.value.toUpperCase())}
            />
          </label>
        </div>
        {error ? <div className="error">{error}</div> : null}
      </section>

      <section className="card">
        <div className="list">
          {items.length === 0 ? (
            <p className="muted">No analysis history yet.</p>
          ) : (
            items.map((item) => (
              <div key={item.id} className="list-item static">
                <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong>
                    {item.stock_symbol} — {item.analysis_type}
                  </strong>
                  <small>
                    Score: {item.final_score} · {item.status}
                  </small>
                </header>
                <p>{item.recommendation || "No recommendation"}</p>
                <footer style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <small>{new Date(item.created_at).toLocaleString()}</small>
                  <div style={{ display: "flex", gap: "0.4rem" }}>
                    <button className="btn ghost" onClick={() => navigate(`/history/${item.id}`)}>
                      Detail
                    </button>
                    <button className="btn ghost" onClick={() => handleDelete(item.id)}>
                      Delete
                    </button>
                  </div>
                </footer>
              </div>
            ))
          )}
        </div>
        {totalPages > 1 && (
          <div className="pagination">
            <button className="btn ghost" disabled={page <= 1} onClick={() => load(page - 1, stockFilter)}>
              Prev
            </button>
            <span>
              Page {page} of {totalPages}
            </span>
            <button className="btn ghost" disabled={page >= totalPages} onClick={() => load(page + 1, stockFilter)}>
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
