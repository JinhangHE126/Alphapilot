import { useEffect, useMemo, useRef, useState } from "react";
import type { ChartPoint } from "../services/sse";

type MiniLineChartProps = {
  data: ChartPoint[];
  width?: number;
  height?: number;
  color?: string;
  emptyLabel?: string;
};

function formatPrice(v: number): string {
  if (v >= 100) return v.toFixed(0);
  if (v >= 10) return v.toFixed(1);
  return v.toFixed(2);
}

function movingAverage(values: number[], window: number): Array<number | null> {
  const out: Array<number | null> = [];
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i];
    if (i >= window) sum -= values[i - window];
    if (i >= window - 1) out.push(sum / window);
    else out.push(null);
  }
  return out;
}

function formatVol(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return `${Math.round(v)}`;
}

type Candle = ChartPoint & {
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
};

export default function MiniLineChart({
  data,
  color = "#60a5fa",
  emptyLabel = "暂无走势数据",
}: MiniLineChartProps) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [chartSize, setChartSize] = useState({ width: 800, height: 360 });

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;

    const updateSize = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width < 1 || height < 1) return;
      setChartSize({
        width: Math.round(width),
        height: Math.round(height),
      });
    };

    updateSize();
    const ro = new ResizeObserver(updateSize);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const width = chartSize.width;
  const height = chartSize.height;
  const padding = { top: 20, right: 54, bottom: 34, left: 44 };
  const volumeHeight = 100;

  const {
    candles,
    candleWidth,
    yTicks,
    maxVolume,
    ma5Path,
    ma20Path,
    lastPrice,
    isUp,
    toX,
    toPriceY,
    chartBottom,
    xTicks,
  } = useMemo(() => {
    if (!data || data.length < 2) {
      return {
        candles: [] as Candle[],
        candleWidth: 4,
        yTicks: [] as number[],
        maxVolume: 0,
        ma5Path: "",
        ma20Path: "",
        lastPrice: null,
        isUp: true,
        toX: (_i: number) => 0,
        toPriceY: (_p: number) => 0,
        chartBottom: 0,
        xTicks: [] as Array<{ idx: number; label: string }>,
      };
    }

    const normalized = data
      .map((d) => ({
        ...d,
        o: Number.isFinite(d.o) ? Number(d.o) : Number(d.c),
        h: Number.isFinite(d.h) ? Number(d.h) : Number(d.c),
        l: Number.isFinite(d.l) ? Number(d.l) : Number(d.c),
        c: Number(d.c),
        v: Number.isFinite(d.v) ? Number(d.v) : 0,
      }))
      .filter((d) => Number.isFinite(d.c));

    if (normalized.length < 2) {
      return {
        candles: [] as Candle[],
        candleWidth: 4,
        yTicks: [] as number[],
        maxVolume: 0,
        ma5Path: "",
        ma20Path: "",
        lastPrice: null,
        isUp: true,
        toX: (_i: number) => 0,
        toPriceY: (_p: number) => 0,
        chartBottom: 0,
        xTicks: [] as Array<{ idx: number; label: string }>,
      };
    }

    const highs = normalized.map((d) => d.h);
    const lows = normalized.map((d) => d.l);
    const closes = normalized.map((d) => d.c);
    const maxP = Math.max(...highs);
    const minP = Math.min(...lows);
    const range = maxP - minP || 1;

    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom - volumeHeight;
    const chartBottomLocal = padding.top + plotH;
    const maxVol = Math.max(...normalized.map((d) => d.v), 1);
    const cWidth = Math.max(2, Math.min(11, (plotW / normalized.length) * 0.62));

    const toXFn = (i: number) =>
      padding.left + (i / Math.max(normalized.length - 1, 1)) * plotW;
    const toYFn = (price: number) =>
      padding.top + ((maxP - price) / range) * plotH;

    const last = closes[closes.length - 1];
    const first = closes[0];
    const change = last - first;

    const ticks: number[] = [];
    for (let i = 0; i <= 3; i++) {
      ticks.push(minP + (range * i) / 3);
    }

    const ma5Vals = movingAverage(closes, 5);
    const ma20Vals = movingAverage(closes, 20);
    const toPath = (arr: Array<number | null>) => {
      let path = "";
      let started = false;
      arr.forEach((v, i) => {
        if (v === null) return;
        const x = toXFn(i);
        const y = toYFn(v);
        if (!started) {
          path += `M ${x.toFixed(1)} ${y.toFixed(1)} `;
          started = true;
        } else {
          path += `L ${x.toFixed(1)} ${y.toFixed(1)} `;
        }
      });
      return path.trim();
    };

    return {
      candles: normalized,
      candleWidth: cWidth,
      lastPrice: last,
      isUp: change >= 0,
      yTicks: ticks,
      maxVolume: maxVol,
      ma5Path: toPath(ma5Vals),
      ma20Path: toPath(ma20Vals),
      toX: toXFn,
    toPriceY: toYFn,
    chartBottom: chartBottomLocal,
    xTicks: [
        { idx: 0, label: normalized[0]?.t ?? "" },
        { idx: Math.floor((normalized.length - 1) / 2), label: normalized[Math.floor((normalized.length - 1) / 2)]?.t ?? "" },
        { idx: normalized.length - 1, label: normalized[normalized.length - 1]?.t ?? "" },
      ],
    };
  }, [data, width, height]);

  const changeColor = isUp ? "#22c55e" : "#ef4444";
  const volTop = chartBottom + 8;
  const volBottom = height - padding.bottom;
  const hoverCandle = hoverIdx !== null && hoverIdx >= 0 && hoverIdx < candles.length ? candles[hoverIdx] : null;
  const hoverPrev = hoverIdx !== null && hoverIdx > 0 ? candles[hoverIdx - 1] : null;
  const hoverDeltaPct = hoverCandle && hoverPrev && hoverPrev.c !== 0
    ? ((hoverCandle.c - hoverPrev.c) / hoverPrev.c) * 100
    : null;
  const currentY = lastPrice !== null ? toPriceY(lastPrice) : 0;
  const currentX = lastPrice !== null ? toX(candles.length - 1) : 0;

  function handleMouseMove(evt: React.MouseEvent<SVGSVGElement>) {
    if (!svgRef.current || candles.length < 2) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((evt.clientX - rect.left) / rect.width) * width;
    const start = padding.left;
    const end = width - padding.right;
    if (x < start || x > end) {
      setHoverIdx(null);
      return;
    }
    const ratio = (x - start) / (end - start);
    const idx = Math.round(ratio * (candles.length - 1));
    setHoverIdx(Math.max(0, Math.min(candles.length - 1, idx)));
  }

  return (
    <div ref={wrapRef} className="mini-chart-wrap">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height="100%"
        preserveAspectRatio="none"
        className="mini-chart-svg"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverIdx(null)}
      >
        {/* Grid lines */}
        {yTicks.map((tick, i) => {
          const y = padding.top + ((chartBottom - padding.top) * (yTicks.length - 1 - i)) / (yTicks.length - 1);
          return (
            <g key={i}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="rgba(148, 163, 184, 0.20)"
                strokeWidth="0.6"
                strokeDasharray="4 4"
              />
              <text
                x={padding.left - 4}
                y={y + 4}
                textAnchor="end"
                fill="var(--text-muted, #9ca3af)"
                fontSize="10"
                fontFamily="system-ui, sans-serif"
              >
                {formatPrice(tick)}
              </text>
            </g>
          );
        })}
        <line
          x1={padding.left}
          y1={chartBottom}
          x2={width - padding.right}
          y2={chartBottom}
          stroke="rgba(148, 163, 184, 0.25)"
          strokeWidth="0.8"
        />

        {/* Candles */}
        {candles.map((d, i) => {
          const x = toX(i);
          const yH = toPriceY(d.h);
          const yL = toPriceY(d.l);
          const yO = toPriceY(d.o);
          const yC = toPriceY(d.c);
          const isBull = d.c >= d.o;
          const bodyTop = Math.min(yO, yC);
          const bodyBottom = Math.max(yO, yC);
          const bodyH = Math.max(1, bodyBottom - bodyTop);
          const candleColor = isBull ? "#16a34a" : "#dc2626";
          return (
            <g key={`${d.t}-${i}`}>
              <line x1={x} y1={yH} x2={x} y2={yL} stroke={candleColor} strokeWidth="1" />
              <rect
                x={x - candleWidth / 2}
                y={bodyTop}
                width={candleWidth}
                height={bodyH}
                fill={isBull ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)"}
                stroke={candleColor}
                strokeWidth="1"
              />
            </g>
          );
        })}

        {/* MA lines */}
        {ma5Path && <path d={ma5Path} fill="none" stroke="#f59e0b" strokeWidth="1.6" />}
        {ma20Path && <path d={ma20Path} fill="none" stroke={color} strokeWidth="1.6" />}

        {/* Volume bars */}
        {candles.map((d, i) => {
          const x = toX(i);
          const h = ((d.v || 0) / maxVolume) * (volBottom - volTop);
          const y = volBottom - h;
          const isBull = d.c >= d.o;
          return (
            <rect
              key={`vol-${d.t}-${i}`}
              x={x - Math.max(1, candleWidth / 2)}
              y={y}
              width={Math.max(1.4, candleWidth)}
              height={Math.max(0.6, h)}
              fill={isBull ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)"}
            />
          );
        })}

        {/* X-axis ticks */}
        {xTicks.map((tick) => (
          <text
            key={`xt-${tick.idx}`}
            x={toX(tick.idx)}
            y={height - 8}
            textAnchor={tick.idx === 0 ? "start" : tick.idx === candles.length - 1 ? "end" : "middle"}
            fill="rgba(148, 163, 184, 0.55)"
            fontSize="10"
            fontFamily="system-ui, sans-serif"
          >
            {tick.label}
          </text>
        ))}

        {/* Current price line and right tag */}
        {lastPrice !== null && (
          <g>
            <line
              x1={padding.left}
              y1={currentY}
              x2={width - padding.right}
              y2={currentY}
              stroke={changeColor}
              strokeWidth="0.9"
              strokeDasharray="5 4"
              opacity="0.8"
            />
            <rect
              x={width - padding.right + 4}
              y={currentY - 9}
              width={44}
              height={18}
              rx={5}
              fill={changeColor}
              opacity="0.92"
            />
            <text
              x={width - padding.right + 26}
              y={currentY + 4}
              textAnchor="middle"
              fill="#0f172a"
              fontSize="10"
              fontWeight="700"
              fontFamily="system-ui, sans-serif"
            >
              {formatPrice(lastPrice)}
            </text>
            <circle cx={currentX} cy={currentY} r={2.5} fill={changeColor} />
          </g>
        )}

        {/* Crosshair */}
        {hoverIdx !== null && hoverIdx >= 0 && hoverIdx < candles.length && (
          <line
            x1={toX(hoverIdx)}
            y1={padding.top}
            x2={toX(hoverIdx)}
            y2={height - padding.bottom}
            stroke="rgba(148, 163, 184, 0.5)"
            strokeWidth="0.8"
            strokeDasharray="3 3"
          />
        )}
      </svg>

      {hoverCandle && (
        <div className="mini-chart-tooltip">
          <div className="mct-row mct-date">{hoverCandle.t}</div>
          <div className="mct-row">O {formatPrice(hoverCandle.o)}  H {formatPrice(hoverCandle.h)}</div>
          <div className="mct-row">L {formatPrice(hoverCandle.l)}  C {formatPrice(hoverCandle.c)}</div>
          <div className="mct-row">V {formatVol(hoverCandle.v)}</div>
          {hoverDeltaPct !== null && (
            <div className="mct-row" style={{ color: hoverDeltaPct >= 0 ? "#22c55e" : "#ef4444" }}>
              {hoverDeltaPct >= 0 ? "+" : ""}
              {hoverDeltaPct.toFixed(2)}%
            </div>
          )}
        </div>
      )}

      {!data || data.length < 2 ? (
        <div className="mini-chart-empty">{emptyLabel}</div>
      ) : null}
    </div>
  );
}
