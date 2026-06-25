import { BarChart3, CircleDollarSign, Percent, ShieldCheck, TrendingDown, TrendingUp, WalletCards } from "lucide-react";
import type { EvidenceFact, EvidencePacketData } from "../services/sse";

type MetricCardProps = {
  label: string;
  value: string;
  sub?: string;
  tone?: "positive" | "negative" | "neutral";
  icon: "money" | "profit" | "eps" | "cash";
  source?: string;
};

type GaugeProps = {
  label: string;
  value: number;
  suffix?: string;
  max?: number;
};

const iconMap = {
  money: CircleDollarSign,
  profit: TrendingUp,
  eps: BarChart3,
  cash: WalletCards,
};

function toNumber(value: EvidenceFact["value"] | undefined): number | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function findFact(facts: EvidenceFact[], fields: string[]): EvidenceFact | undefined {
  return facts.find((fact) => fields.includes(fact.field) && toNumber(fact.value) !== undefined);
}

function findNonZeroFact(facts: EvidenceFact[], fields: string[]): EvidenceFact | undefined {
  return facts.find((fact) => {
    const value = toNumber(fact.value);
    return fields.includes(fact.field) && value !== undefined && value !== 0;
  });
}

function growthText(value?: number): string | undefined {
  if (value === undefined || value === 0) return undefined;
  return `同比 ${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function toneFromValue(value?: number, positiveIsGood = true): "positive" | "negative" | "neutral" {
  if (value === undefined || value === 0) return "neutral";
  const isPositive = value > 0;
  return isPositive === positiveIsGood ? "positive" : "negative";
}

function formatCurrency(value?: number, unit?: string): string {
  if (value === undefined) return "";

  const abs = Math.abs(value);
  const currency = unit && unit !== "number" && unit !== "ratio" && unit !== "percent" ? unit : "";
  if (abs >= 1_000_000_000) return `${currency} ${(value / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${currency} ${(value / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${currency} ${(value / 1_000).toFixed(2)}K`;
  return `${currency} ${value.toFixed(2)}`.trim();
}

function formatPercent(value?: number): string {
  if (value === undefined) return "";
  return `${value.toFixed(2)}%`;
}

function MetricCard({ label, value, sub, tone = "neutral", icon, source }: MetricCardProps) {
  const Icon = iconMap[icon];
  const TrendIcon = tone === "negative" ? TrendingDown : TrendingUp;
  return (
    <div className={`fin-metric-card ${tone}`}>
      <div className="fin-metric-icon">
        <Icon size={16} />
      </div>
      <div className="fin-metric-body">
        <span className="fin-metric-label">{label}</span>
        <span className="fin-metric-value">{value}</span>
        {sub && (
          <span className={`fin-metric-sub trend ${tone}`}>
            <TrendIcon size={11} />
            {sub}
          </span>
        )}
        {source && <span className="fin-metric-source">源: {source}</span>}
      </div>
    </div>
  );
}

function Gauge({ label, value, suffix = "%", max = 100 }: GaugeProps) {
  const width = Math.max(0, Math.min(100, (Math.abs(value) / max) * 100));
  const barColor = value >= 0 ? "rgba(34, 197, 94, 0.7)" : "rgba(248, 113, 113, 0.7)";

  return (
    <div className="fin-gauge">
      <div className="fin-gauge-header">
        <span className="fin-gauge-label">{label}</span>
        <span className="fin-gauge-value">{value.toFixed(2)}{suffix}</span>
      </div>
      <div className="fin-gauge-bar-wrap">
        <div className="fin-gauge-bar" style={{ width: `${width}%`, background: barColor }} />
      </div>
    </div>
  );
}

function HealthItem({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "positive" | "negative" | "neutral" }) {
  return (
    <div className={`fin-health-item ${tone}`}>
      <span className="fin-health-label">{label}</span>
      <span className="fin-health-value">{value}</span>
    </div>
  );
}

function computeHealthScore(values: {
  netMargin?: number;
  roe?: number;
  operatingCashFlow?: number;
  freeCashFlow?: number;
  debtToEquity?: number;
  cashPosition?: number;
  totalDebt?: number;
}): number | undefined {
  const signals: number[] = [];

  if (values.netMargin !== undefined) signals.push(values.netMargin > 0 ? 1 : 0);
  if (values.roe !== undefined) signals.push(values.roe > 0 ? 1 : 0);
  if (values.operatingCashFlow !== undefined) signals.push(values.operatingCashFlow > 0 ? 1 : 0);
  if (values.freeCashFlow !== undefined) signals.push(values.freeCashFlow > 0 ? 1 : 0);
  if (values.debtToEquity !== undefined) signals.push(values.debtToEquity < 100 ? 1 : values.debtToEquity < 200 ? 0.5 : 0);
  if (values.cashPosition !== undefined && values.totalDebt !== undefined && values.totalDebt > 0) {
    signals.push(values.cashPosition / values.totalDebt >= 1 ? 1 : 0.4);
  }

  if (signals.length < 3) return undefined;
  return Math.round((signals.reduce((sum, signal) => sum + signal, 0) / signals.length) * 100);
}

export default function FinancialTrendsPanel({ evidence }: { evidence: EvidencePacketData }) {
  const facts = evidence.facts || [];

  const revenueFact = findNonZeroFact(facts, ["revenue", "revenue_ttm", "total_revenue"]);
  const netProfitFact = findNonZeroFact(facts, ["net_profit", "net_income"]);
  const epsFact = findNonZeroFact(facts, ["eps", "eps_basic", "trailing_eps"]);
  const operatingCashFlowFact = findNonZeroFact(facts, ["operating_cash_flow", "operating_cashflow"]);
  const freeCashFlowFact = findNonZeroFact(facts, ["free_cash_flow", "free_cashflow"]);
  const cashPositionFact = findNonZeroFact(facts, ["cash_position", "total_cash"]);
  const totalDebtFact = findNonZeroFact(facts, ["total_debt"]);
  const netDebtFact = findFact(facts, ["net_debt"]);
  const revenueGrowthFact = findFact(facts, ["revenue_growth_yoy"]);
  const netProfitGrowthFact = findFact(facts, ["net_profit_growth_yoy", "net_income_growth_yoy"]);
  const epsGrowthFact = findFact(facts, ["eps_growth_yoy"]);
  const grossMarginFact = findFact(facts, ["gross_margin"]);
  const operatingMarginFact = findFact(facts, ["operating_margin"]);
  const netMarginFact = findFact(facts, ["net_margin"]);
  const roeFact = findFact(facts, ["return_on_equity", "roe"]);
  const debtToAssetsFact = findFact(facts, ["debt_to_assets"]);
  const debtToEquityFact = findFact(facts, ["debt_to_equity"]);

  const revenue = toNumber(revenueFact?.value);
  const netProfit = toNumber(netProfitFact?.value);
  const eps = toNumber(epsFact?.value);
  const operatingCashFlow = toNumber(operatingCashFlowFact?.value);
  const freeCashFlow = toNumber(freeCashFlowFact?.value);
  const cashPosition = toNumber(cashPositionFact?.value);
  const totalDebt = toNumber(totalDebtFact?.value);
  const netDebt = toNumber(netDebtFact?.value);
  const revenueGrowth = toNumber(revenueGrowthFact?.value);
  const netProfitGrowth = toNumber(netProfitGrowthFact?.value);
  const epsGrowth = toNumber(epsGrowthFact?.value);
  const grossMargin = toNumber(grossMarginFact?.value);
  const operatingMargin = toNumber(operatingMarginFact?.value);
  const netMargin = toNumber(netMarginFact?.value);
  const roe = toNumber(roeFact?.value);
  const debtToAssets = toNumber(debtToAssetsFact?.value);
  const debtToEquity = toNumber(debtToEquityFact?.value);
  const healthScore = computeHealthScore({
    netMargin,
    roe,
    operatingCashFlow,
    freeCashFlow,
    debtToEquity,
    cashPosition,
    totalDebt,
  });

  const keyMetrics: MetricCardProps[] = [];
  if (revenue !== undefined) {
    keyMetrics.push({
      label: "营收",
      value: formatCurrency(revenue, revenueFact?.unit),
      sub: growthText(revenueGrowth),
      tone: toneFromValue(revenueGrowth),
      icon: "money" as const,
      source: revenueFact?.source,
    });
  }
  if (netProfit !== undefined) {
    keyMetrics.push({
      label: "净利润",
      value: formatCurrency(netProfit, netProfitFact?.unit || revenueFact?.unit),
      sub: growthText(netProfitGrowth),
      tone: toneFromValue(netProfitGrowth ?? netProfit),
      icon: "profit" as const,
      source: netProfitFact?.source,
    });
  }
  if (eps !== undefined) {
    keyMetrics.push({
      label: "EPS",
      value: eps.toFixed(2),
      sub: growthText(epsGrowth),
      tone: toneFromValue(epsGrowth ?? eps),
      icon: "eps" as const,
      source: epsFact?.source,
    });
  }
  if (operatingCashFlow !== undefined) {
    keyMetrics.push({
      label: "经营现金流",
      value: formatCurrency(operatingCashFlow, operatingCashFlowFact?.unit || revenueFact?.unit),
      sub: operatingCashFlow > 0 ? "现金流为正" : "现金流为负",
      tone: toneFromValue(operatingCashFlow),
      icon: "cash" as const,
      source: operatingCashFlowFact?.source,
    });
  }

  const profitabilityRatios = [
    { label: "毛利率", value: grossMargin },
    { label: "营业利润率", value: operatingMargin },
    { label: "净利率", value: netMargin },
    { label: "ROE", value: roe },
  ].filter((item): item is { label: string; value: number } => item.value !== undefined);

  const healthItems = [
    { label: "资产负债率", value: debtToAssets },
    { label: "债务权益比", value: debtToEquity },
  ].filter((item): item is { label: string; value: number } => item.value !== undefined);

  return (
    <div className="fin-trends">
      <div className="fin-trends-header">
        <span className="fin-trends-title">
          <BarChart3 size={16} />
          财务基本面快照
        </span>
        <span className="fin-trends-badge">Latest Facts</span>
      </div>
      <p className="fin-trends-subtitle">
        展示当前 Evidence Packet 中已有的最新期财务事实；历史趋势图暂不启用，缺失字段不做占位。
      </p>

      {keyMetrics.length > 0 && (
        <div className="fin-metrics-row">
          {keyMetrics.map((metric) => (
            <MetricCard key={metric.label} {...metric} />
          ))}
        </div>
      )}

      {profitabilityRatios.length > 0 && (
        <div className="fin-gauges-section">
          <div className="fin-section-label">
            <Percent size={13} />
            盈利能力
          </div>
          <div className="fin-gauges-grid">
            {profitabilityRatios.map((ratio) => (
              <Gauge key={ratio.label} label={ratio.label} value={ratio.value} />
            ))}
          </div>
        </div>
      )}

      {(healthItems.length > 0 || cashPosition !== undefined || totalDebt !== undefined || freeCashFlow !== undefined || healthScore !== undefined) && (
        <div className="fin-health-section">
          <div className="fin-section-label">
            <ShieldCheck size={13} />
            财务健康度
          </div>
          <div className="fin-health-grid">
            {healthScore !== undefined && (
              <div className={`fin-health-score ${healthScore >= 70 ? "positive" : healthScore >= 45 ? "neutral" : "negative"}`}>
                <span className="fin-health-score-label">健康评分</span>
                <strong>{healthScore}</strong>
                <span>/100</span>
              </div>
            )}
            {cashPosition !== undefined && (
              <HealthItem label="现金储备" value={formatCurrency(cashPosition, cashPositionFact?.unit || revenueFact?.unit)} tone="positive" />
            )}
            {totalDebt !== undefined && (
              <HealthItem label="总债务" value={formatCurrency(totalDebt, totalDebtFact?.unit || revenueFact?.unit)} tone={totalDebt > 0 ? "negative" : "positive"} />
            )}
            {netDebt !== undefined && (
              <HealthItem label="净债务" value={formatCurrency(netDebt, netDebtFact?.unit || revenueFact?.unit)} tone={netDebt <= 0 ? "positive" : "negative"} />
            )}
            {freeCashFlow !== undefined && (
              <HealthItem label="自由现金流" value={formatCurrency(freeCashFlow, freeCashFlowFact?.unit || revenueFact?.unit)} tone={toneFromValue(freeCashFlow)} />
            )}
            {healthItems.map((item) => (
              <HealthItem
                key={item.label}
                label={item.label}
                value={formatPercent(item.value)}
                tone={toneFromValue(item.value, false)}
              />
            ))}
          </div>
        </div>
      )}

      {/* 数据来源汇总 */}
      <FinSources facts={facts} />
    </div>
  );
}

function FinSources({ facts }: { facts: EvidencePacketData["facts"] }) {
  // 所有当前展示指标用到的 field
  const displayedFields = new Set([
    "revenue", "total_revenue", "net_profit", "net_income", "eps", "eps_basic", "trailing_eps",
    "operating_cash_flow", "operating_cashflow", "free_cash_flow", "free_cashflow",
    "cash_position", "total_cash", "total_debt", "net_debt",
    "revenue_growth_yoy", "net_profit_growth_yoy", "net_income_growth_yoy", "eps_growth_yoy",
    "gross_margin", "operating_margin", "net_margin",
    "return_on_equity", "roe", "debt_to_assets", "debt_to_equity",
  ]);

  const relevantFacts = facts.filter((f) => displayedFields.has(f.field));
  const sources = [...new Set(relevantFacts.map((f) => f.source || "unknown"))].sort();

  if (sources.length === 0) return null;

  return (
    <div className="fin-sources">
      <span className="fin-sources-label">数据来源</span>
      {sources.map((s) => (
        <span key={s} className="fin-source-badge">{s}</span>
      ))}
    </div>
  );
}
