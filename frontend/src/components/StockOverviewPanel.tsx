import { useMemo, useState } from "react";
import MiniLineChart from "./MiniLineChart";
import type { EvidencePacketData } from "../services/sse";
import { TrendingUp, TrendingDown, Activity, DollarSign, BarChart3, Gauge, Timer } from "lucide-react";

type StockOverviewPanelProps = {
  data: EvidencePacketData | null;
  stockSymbol: string;
};

type MetricItem = {
  label: string;
  value: string;
  sub?: string;
  source?: string;
  icon: React.ReactNode;
  color: string;
};

type RangeKey = "1M" | "3M" | "6M" | "1Y" | "MAX";

function fmtPrice(v: number): string {
  if (v >= 100) return v.toFixed(0);
  if (v >= 10) return v.toFixed(1);
  return v.toFixed(2);
}

function maLast(data: EvidencePacketData["chart_data"], window: number): number | null {
  const closes = data.map((d) => Number(d.c)).filter((v) => Number.isFinite(v));
  if (closes.length < window) return null;
  const slice = closes.slice(-window);
  return slice.reduce((sum, v) => sum + v, 0) / slice.length;
}

function fmtNum(v: number | string): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (isNaN(n)) return String(v);
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1000) return n.toLocaleString();
  if (n % 1 === 0) return n.toString();
  return n.toFixed(2);
}

function getFact(facts: EvidencePacketData["facts"], field: string) {
  return facts?.find((x) => x.field === field);
}

function getFactVal(facts: EvidencePacketData["facts"], field: string): string | undefined {
  const f = getFact(facts, field);
  if (!f) return undefined;
  return String(f.value);
}

function getFactSource(facts: EvidencePacketData["facts"], field: string): string | undefined {
  const f = getFact(facts, field);
  if (!f || !f.source) return undefined;
  return f.source;
}

export default function StockOverviewPanel({ data, stockSymbol }: StockOverviewPanelProps) {
  const [range, setRange] = useState<RangeKey>("3M");
  const facts = data?.facts ?? [];
  const chartRaw = data?.chart_data ?? [];

  const metrics = useMemo(() => {
    const items: MetricItem[] = [];
    const price = getFactVal(facts, "current_price");
    const changePct = getFactVal(facts, "price_change_pct");
    const changeNum = changePct ? parseFloat(changePct) : 0;

    items.push({
      label: "最新价",
      value: price ?? "N/A",
      sub: changePct ? `${changeNum >= 0 ? "+" : ""}${changePct}%` : undefined,
      source: getFactSource(facts, "current_price"),
      icon: <DollarSign size={16} />,
      color: changeNum >= 0 ? "#22c55e" : "#ef4444",
    });

    const marketCap = getFactVal(facts, "market_cap") ?? getFactVal(facts, "circulating_market_cap");
    const marketCapSource = getFactSource(facts, "market_cap") ?? getFactSource(facts, "circulating_market_cap");
    items.push({
      label: "市值",
      value: marketCap ? fmtNum(marketCap) : "N/A",
      source: marketCapSource,
      icon: <BarChart3 size={16} />,
      color: "#60a5fa",
    });

    const pe = getFactVal(facts, "pe_ratio") ?? getFactVal(facts, "forward_pe");
    const peSource = getFactSource(facts, "pe_ratio") ?? getFactSource(facts, "forward_pe");
    items.push({
      label: "市盈率",
      value: pe ?? "N/A",
      source: peSource,
      icon: <Activity size={16} />,
      color: "#a78bfa",
    });

    const vol = getFactVal(facts, "volatility_20d_annualized");
    items.push({
      label: "波动率(20日)",
      value: vol ? `${vol}%` : "N/A",
      source: getFactSource(facts, "volatility_20d_annualized"),
      icon: <Gauge size={16} />,
      color: "#f59e0b",
    });

    const rsi = getFactVal(facts, "rsi_14");
    items.push({
      label: "RSI (14)",
      value: rsi ?? "N/A",
      source: getFactSource(facts, "rsi_14"),
      icon: rsi && parseFloat(rsi) > 70 ? <TrendingDown size={16} /> : <TrendingUp size={16} />,
      color: rsi
        ? parseFloat(rsi) > 70
          ? "#ef4444"
          : parseFloat(rsi) < 30
            ? "#22c55e"
            : "#6b7280"
        : "#6b7280",
    });

    const macd = getFactVal(facts, "macd");
    const macdSig = getFactVal(facts, "macd_signal");
    const macdVal = macd ? parseFloat(macd).toFixed(3) : undefined;
    const macdSub = macdSig ? `信号 ${parseFloat(macdSig).toFixed(3)}` : undefined;
    items.push({
      label: "MACD",
      value: macdVal ?? "N/A",
      sub: macdSub,
      source: getFactSource(facts, "macd"),
      icon: <Timer size={16} />,
      color: macd && parseFloat(macd) >= 0 ? "#22c55e" : "#ef4444",
    });

    return items;
  }, [facts]);

  const updatedAt = useMemo(() => {
    const f = facts.find((x) => x.as_of_date);
    return f?.as_of_date ?? "";
  }, [facts]);

  const chartSource = useMemo(() => {
    const sourceCount = new Map<string, number>();
    for (const f of facts) {
      if (!f.source) continue;
      sourceCount.set(f.source, (sourceCount.get(f.source) ?? 0) + 1);
    }
    return [...sourceCount.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "N/A";
  }, [facts]);

  const chartData = useMemo(() => {
    const len = chartRaw.length;
    if (len <= 1) return chartRaw;
    const pointsMap: Record<RangeKey, number> = {
      "1M": 22,
      "3M": 66,
      "6M": 132,
      "1Y": 264,
      "MAX": Number.MAX_SAFE_INTEGER,
    };
    const take = pointsMap[range];
    return take >= len ? chartRaw : chartRaw.slice(len - take);
  }, [chartRaw, range]);

  const priceMetric = metrics[0];
  const ma5 = maLast(chartData, 5);
  const ma20 = maLast(chartData, 20);

  return (
    <div className="stock-overview">
      <div className="so-chart">
        <div className="so-chart-toolbar">
          <div className="so-toolbar-left">
            <span className="so-chart-title">{stockSymbol}</span>
            <span className="so-toolbar-price">{priceMetric?.value ?? "N/A"}</span>
            {priceMetric?.sub && (
              <span
                className={`so-toolbar-change ${priceMetric.sub.startsWith("-") ? "down" : "up"}`}
              >
                {priceMetric.sub}
              </span>
            )}
          </div>
          <div className="so-toolbar-center">
            <span className="so-legend-item ma5">MA5 {ma5 !== null ? fmtPrice(ma5) : "--"}</span>
            <span className="so-legend-item ma20">MA20 {ma20 !== null ? fmtPrice(ma20) : "--"}</span>
          </div>
          <div className="so-range-switch">
            {(["1M", "3M", "6M", "1Y", "MAX"] as const).map((r) => (
              <button
                key={r}
                type="button"
                className={`so-range-btn ${range === r ? "active" : ""}`}
                onClick={() => setRange(r)}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <div className="so-chart-canvas">
          <MiniLineChart data={chartData} color="#3b82f6" emptyLabel="暂无K线数据" />
        </div>
        <div className="so-chart-footer">
          <span>Source: {chartSource}</span>
          <span>{updatedAt ? `Updated: ${updatedAt}` : "Updated: N/A"}</span>
          <span>{`Range: ${range}`}</span>
          <span>{`Points: ${chartData.length}`}</span>
        </div>
      </div>

      <div className="so-metrics">
        <div className="so-metrics-header">
          <span className="so-symbol">{stockSymbol}</span>
          {updatedAt && <span className="so-updated">数据日期: {updatedAt}</span>}
        </div>
        <div className="so-metrics-grid">
          {metrics.map((m, i) => (
            <div key={i} className="so-metric-card">
              <div className="so-metric-icon" style={{ color: m.color }}>
                {m.icon}
              </div>
              <div className="so-metric-body">
                <span className="so-metric-label">{m.label}</span>
                <span className="so-metric-value" style={{ color: i === 0 ? m.color : undefined }}>
                  {m.value}
                </span>
                {m.sub && <span className="so-metric-sub">{m.sub}</span>}
                {m.source && <span className="so-metric-source">源: {m.source}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
