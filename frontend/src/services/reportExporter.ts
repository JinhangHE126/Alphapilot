import type { EvidencePacketData, GuardCheck, RiskLevelData, TargetPriceData } from "../services/sse";

/** Agent 状态的子集 — reportExporter 只需要 agent/content/label */
type AgentInfo = {
  agent: string;
  label: string;
  icon: string;
  status: string;
  content: string;
  startedAt?: number;
  finishedAt?: number;
};

/* ══════════════════════════════════════════════════════════════════════
   报告生成器 — 将分析结果组装为 Markdown，触发浏览器下载
   ══════════════════════════════════════════════════════════════════════ */

type ReportInput = {
  stockSymbol: string;
  finalReport: string;
  recommendation: string;
  evidence: EvidencePacketData | null;
  guard: GuardCheck | null;
  riskLevel: RiskLevelData | null;
  targetPrice: TargetPriceData | null;
  agents: AgentInfo[];
};

function fmtTimestamp(): string {
  return new Date().toISOString().replace("T", " ").split(".")[0];
}

function fmtFactValue(v: number | string, unit?: string): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (isNaN(n)) return String(v);
  if (unit === "percent") return n.toFixed(2) + "%";
  if (Math.abs(n) >= 1e12) return (n / 1e12).toFixed(2) + "万亿";
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(1) + "亿";
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + "万";
  if (Number.isInteger(n)) return n.toLocaleString();
  return n.toFixed(2);
}

const FIELD_NAME: Record<string, string> = {
  current_price: "当前价", price_change_pct: "涨跌幅",
  revenue: "营收", total_revenue: "营收", net_profit: "净利润", net_income: "净利润",
  eps: "EPS", eps_basic: "EPS", trailing_eps: "EPS",
  gross_margin: "毛利率", net_margin: "净利率", operating_margin: "营业利润率",
  return_on_equity: "ROE", roe: "ROE",
  debt_to_assets: "资产负债率", debt_to_equity: "负债权益比",
  market_cap: "市值", pe_ratio: "PE", pb_ratio: "PB",
  ps_ratio: "PS", ev_to_ebitda: "EV/EBITDA", dividend_yield: "股息率",
  rsi_14: "RSI(14)", macd: "MACD",
  volatility_20d_annualized: "年化波动率", ma_20: "MA20", ma_50: "MA50", ma_200: "MA200",
  sharpe_ratio_annual: "夏普比率", max_drawdown: "最大回撤",
  var_95_daily: "VaR(95%)", sortino_ratio_annual: "索提诺比率",
  news_score: "新闻评分", news_sentiment: "新闻情绪",
  operating_cash_flow: "经营现金流", operating_cashflow: "经营现金流",
  free_cash_flow: "自由现金流", free_cashflow: "自由现金流",
  cash_position: "现金储备", total_cash: "现金储备",
  total_debt: "总债务", net_debt: "净债务",
  revenue_growth_yoy: "营收增速", net_profit_growth_yoy: "净利润增速",
  net_income_growth_yoy: "净利润增速", eps_growth_yoy: "EPS增速",
};

export function generateMarkdownReport(input: ReportInput): string {
  const { stockSymbol, finalReport, recommendation, evidence, guard, riskLevel, targetPrice, agents } = input;

  const lines: string[] = [];

  // ── 头部 ──
  lines.push(`# AlphaPilot 分析报告 — ${stockSymbol}`);
  lines.push("");
  lines.push(`**生成时间**: ${fmtTimestamp()}`);
  lines.push(`**数据来源**: ${[...new Set((evidence?.facts ?? []).map((f) => f.source || "unknown"))].join(", ") || "N/A"}`);
  lines.push("");

  // ── 关键指标 ──
  lines.push("## 关键指标");
  lines.push("");
  const facts = evidence?.facts ?? [];
  const keyFields = [
    "current_price", "price_change_pct", "market_cap", "pe_ratio", "pb_ratio",
    "revenue", "net_profit", "eps", "gross_margin", "net_margin", "return_on_equity",
    "debt_to_assets", "volatility_20d_annualized", "max_drawdown", "sharpe_ratio_annual",
    "eps_growth_yoy", "revenue_growth_yoy",
  ];
  const keyFacts = facts.filter((f) => keyFields.includes(f.field));

  if (keyFacts.length > 0) {
    lines.push("| 指标 | 数值 | 来源 |");
    lines.push("|------|------|------|");
    for (const f of keyFacts) {
      lines.push(`| ${FIELD_NAME[f.field] || f.field} | ${fmtFactValue(f.value, f.unit)} | ${f.source || "-"} |`);
    }
    lines.push("");
  }

  // ── 估值与目标价 ──
  if (targetPrice) {
    lines.push("## 估值与目标价");
    lines.push("");
    lines.push("| 项目 | 内容 |");
    lines.push("|------|------|");
    if (targetPrice.target_price_mid !== null && targetPrice.target_price_mid !== undefined) lines.push(`| 目标价（中性） | ${targetPrice.target_price_mid} |`);
    if (targetPrice.target_price_low !== null && targetPrice.target_price_low !== undefined) lines.push(`| 目标价（悲观） | ${targetPrice.target_price_low} |`);
    if (targetPrice.target_price_high !== null && targetPrice.target_price_high !== undefined) lines.push(`| 目标价（乐观） | ${targetPrice.target_price_high} |`);
    if (targetPrice.upside_pct !== null && targetPrice.upside_pct !== undefined) lines.push(`| 上行空间 | ${targetPrice.upside_pct}% |`);
    if (targetPrice.downside_pct !== null && targetPrice.downside_pct !== undefined) lines.push(`| 下行风险 | ${targetPrice.downside_pct}% |`);
    if (targetPrice.consensus_summary) lines.push(`| 共识摘要 | ${targetPrice.consensus_summary} |`);
    lines.push("");
  }

  // ── 风险评估 ──
  if (riskLevel) {
    lines.push("## 风险评估");
    lines.push("");
    const score = riskLevel.overall_risk_score ?? 0;
    const level = score <= 30 ? "低风险" : score <= 60 ? "中等风险" : "高风险";
    lines.push(`- **风险等级**: ${level}（${score}/100）`);
    if (riskLevel.volatility_risk) lines.push(`- **波动风险**: ${riskLevel.volatility_risk}`);
    if (riskLevel.macro_risk) lines.push(`- **宏观风险**: ${riskLevel.macro_risk}`);
    if (riskLevel.stop_loss_suggestion) lines.push(`- **建议止损**: ${riskLevel.stop_loss_suggestion}`);
    if (riskLevel.position_suggestion) lines.push(`- **建议仓位**: ${riskLevel.position_suggestion}`);
    if (riskLevel.key_risks && riskLevel.key_risks.length > 0) {
      lines.push(`- **关键风险点**:`);
      for (const r of riskLevel.key_risks) {
        lines.push(`  - ${r}`);
      }
    }
    if (riskLevel.risk_reasoning) {
      lines.push("");
      lines.push("### 风险分析");
      lines.push("");
      lines.push(riskLevel.risk_reasoning);
    }
    lines.push("");
  }

  // ── Guard 校验 ──
  if (guard) {
    lines.push("## Guard 校验");
    lines.push("");
    lines.push(`- **结论**: ${guard.is_valid ? "通过" : "未通过"}`);
    lines.push(`- **置信度**: ${guard.confidence_score}/100`);
    if (guard.checks) {
      for (const [key, c] of Object.entries(guard.checks)) {
        const label = key === "data_coverage" ? "数据覆盖" :
          key === "symbol_match" ? "标的匹配" :
          key === "unsupported_claim" ? "无依据声明" : key;
        lines.push(`- **${label}**: ${c.passed ? "通过" : "未通过"}`);
        if (c.detail) lines.push(`  - ${c.detail}`);
      }
    }
    if (guard.issues && guard.issues.length > 0) {
      lines.push("");
      lines.push("### 发现的问题");
      for (const iss of guard.issues) {
        lines.push(`- ${iss}`);
      }
    }
    if (guard.risk_warnings && guard.risk_warnings.length > 0) {
      lines.push("");
      lines.push("### 风险提示");
      for (const w of guard.risk_warnings) {
        lines.push(`- ${w}`);
      }
    }
    if (guard.final_reasoning) {
      lines.push("");
      lines.push("### Guard 推理");
      lines.push("");
      lines.push(guard.final_reasoning);
    }
    lines.push("");
  }

  // ── 最终报告 ──
  lines.push("## 最终分析报告");
  lines.push("");
  lines.push(finalReport || "报告尚未生成");
  lines.push("");

  // ── 投资建议 ──
  if (recommendation && recommendation !== finalReport) {
    lines.push("## 投资建议");
    lines.push("");
    lines.push(recommendation);
    lines.push("");
  }

  // ── Agent 输出摘要 ──
  const outputAgents = agents.filter((a) => a.content && a.content.trim().length > 0);
  if (outputAgents.length > 0) {
    lines.push("## Agent 输出详情");
    lines.push("");
    for (const a of outputAgents) {
      lines.push(`### ${a.label}`);
      lines.push("");
      // 截断过长内容
      const maxLen = 3000;
      const body = a.content.length > maxLen ? a.content.slice(0, maxLen) + "\n\n*(内容过长已截断)*" : a.content;
      lines.push(body);
      lines.push("");
    }
  }

  // ── 页脚 ──
  lines.push("---");
  lines.push(`*本报告由 AlphaPilot 自动生成于 ${fmtTimestamp()}。数据仅供参考，不构成投资建议。*`);

  return lines.join("\n");
}

/** 触发浏览器下载 Markdown 文件 */
export function downloadMarkdownReport(markdown: string, stockSymbol: string): void {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `AlphaPilot_${stockSymbol}_${new Date().toISOString().split("T")[0]}.md`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/* ══════════════════════════════════════════════════════════════════════
   PDF 导出 — html2canvas + jsPDF
   ══════════════════════════════════════════════════════════════════════ */

const PDF_STYLE = `
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif; background: #0d1117; color: #e6edf3; padding: 32px 40px; line-height: 1.65; }
    h1 { font-size: 22px; font-weight: 800; color: #f0f6fc; margin-bottom: 4px; }
    .meta { font-size: 11px; color: #8b949e; margin-bottom: 24px; }
    h2 { font-size: 15px; font-weight: 700; color: #f0f6fc; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 4px; margin: 28px 0 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 11px; margin: 8px 0 14px; }
    th { text-align: left; padding: 6px 8px; background: rgba(255,255,255,0.04); font-weight: 600; color: #8b949e; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; border-bottom: 1px solid rgba(255,255,255,0.08); }
    td { padding: 5px 8px; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 11px; }
    ul, ol { padding-left: 20px; margin: 6px 0 12px; font-size: 12px; }
    li { margin-bottom: 3px; }
    p { font-size: 12px; margin: 6px 0; }
    .risk-level { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; }
    .risk-low { color: #22c55e; background: rgba(34,197,94,0.1); }
    .risk-mid { color: #f59e0b; background: rgba(245,158,11,0.1); }
    .risk-high{ color: #ef4444; background: rgba(239,68,68,0.1); }
    .badge { display: inline-block; font-size: 9px; color: #8b949e; background: rgba(255,255,255,0.06); padding: 1px 6px; border-radius: 999px; margin-right: 4px; }
    .footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.06); font-size: 10px; color: #484f58; text-align: center; }
    .block { margin: 10px 0; padding: 10px 14px; border-radius: 8px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); }
    .block p { margin: 2px 0; font-size: 12px; }
  </style>`;

function _buildReportHTML(input: ReportInput): string {
  const { stockSymbol, finalReport, recommendation, evidence, guard, riskLevel, targetPrice } = input;
  const facts = evidence?.facts ?? [];
  const dateStr = new Date().toISOString().split("T")[0];

  let h = PDF_STYLE;
  h += `<body>`;

  // 标题
  h += `<h1>AlphaPilot 分析报告 — ${stockSymbol}</h1>`;
  h += `<div class="meta">生成时间: ${fmtTimestamp()} &nbsp;|&nbsp; 数据来源: ${[...new Set(facts.map(f => f.source || "unknown"))].join(", ") || "N/A"}</div>`;

  // 关键指标
  const keyFields = ["current_price","price_change_pct","market_cap","pe_ratio","pb_ratio","revenue","net_profit","eps","gross_margin","net_margin","return_on_equity","debt_to_assets","volatility_20d_annualized","max_drawdown","sharpe_ratio_annual","eps_growth_yoy","revenue_growth_yoy"];
  const keyFacts = facts.filter(f => keyFields.includes(f.field));
  if (keyFacts.length > 0) {
    h += `<h2>关键指标</h2><table><tr><th>指标</th><th>数值</th><th>来源</th></tr>`;
    for (const f of keyFacts) {
      h += `<tr><td>${FIELD_NAME[f.field] || f.field}</td><td>${fmtFactValue(f.value, f.unit)}</td><td>${f.source || "-"}</td></tr>`;
    }
    h += `</table>`;
  }

  // 估值
  if (targetPrice) {
    h += `<h2>估值与目标价</h2><table>`;
    if (targetPrice.target_price_mid != null) h += `<tr><td>目标价（中性）</td><td>${targetPrice.target_price_mid}</td></tr>`;
    if (targetPrice.target_price_low != null) h += `<tr><td>目标价（悲观）</td><td>${targetPrice.target_price_low}</td></tr>`;
    if (targetPrice.target_price_high != null) h += `<tr><td>目标价（乐观）</td><td>${targetPrice.target_price_high}</td></tr>`;
    if (targetPrice.upside_pct != null) h += `<tr><td>上行空间</td><td>${targetPrice.upside_pct}%</td></tr>`;
    if (targetPrice.downside_pct != null) h += `<tr><td>下行风险</td><td>${targetPrice.downside_pct}%</td></tr>`;
    if (targetPrice.consensus_summary) h += `<tr><td>共识摘要</td><td>${targetPrice.consensus_summary}</td></tr>`;
    h += `</table>`;
  }

  // 风险
  if (riskLevel) {
    const score = riskLevel.overall_risk_score ?? 0;
    const level = score <= 30 ? "低风险" : score <= 60 ? "中等风险" : "高风险";
    const cls = score <= 30 ? "risk-low" : score <= 60 ? "risk-mid" : "risk-high";
    h += `<h2>风险评估</h2>`;
    h += `<p><span class="risk-level ${cls}">${level}（${score}/100）</span></p>`;
    if (riskLevel.volatility_risk) h += `<p>波动风险: ${riskLevel.volatility_risk}</p>`;
    if (riskLevel.macro_risk) h += `<p>宏观风险: ${riskLevel.macro_risk}</p>`;
    if (riskLevel.stop_loss_suggestion) h += `<p>建议止损: ${riskLevel.stop_loss_suggestion}</p>`;
    if (riskLevel.position_suggestion) h += `<p>建议仓位: ${riskLevel.position_suggestion}</p>`;
    if (riskLevel.key_risks?.length) {
      h += `<p><strong>关键风险点:</strong></p><ul>${riskLevel.key_risks.map(r => `<li>${r}</li>`).join("")}</ul>`;
    }
    if (riskLevel.risk_reasoning) {
      h += `<div class="block"><p><strong>风险分析</strong></p><p>${riskLevel.risk_reasoning}</p></div>`;
    }
  }

  // Guard
  if (guard) {
    h += `<h2>Guard 校验</h2>`;
    h += `<p>结论: ${guard.is_valid ? "通过" : "未通过"} &nbsp;|&nbsp; 置信度: ${guard.confidence_score}/100</p>`;
    if (guard.checks) {
      h += `<table><tr><th>检查项</th><th>状态</th><th>详情</th></tr>`;
      for (const [k, c] of Object.entries(guard.checks)) {
        const label = k === "data_coverage" ? "数据覆盖" : k === "symbol_match" ? "标的匹配" : k === "unsupported_claim" ? "无依据声明" : k;
        h += `<tr><td>${label}</td><td style="color:${c.passed ? '#22c55e' : '#ef4444'}">${c.passed ? "通过" : "未通过"}</td><td>${c.detail || ""}</td></tr>`;
      }
      h += `</table>`;
    }
    if (guard.issues?.length) h += `<p><strong>发现问题:</strong></p><ul>${guard.issues.map(i => `<li>${i}</li>`).join("")}</ul>`;
    if (guard.risk_warnings?.length) h += `<p><strong>风险提示:</strong></p><ul>${guard.risk_warnings.map(w => `<li>${w}</li>`).join("")}</ul>`;
    if (guard.final_reasoning) h += `<div class="block"><p><strong>Guard 推理</strong></p><p>${guard.final_reasoning}</p></div>`;
  }

  // 最终报告
  h += `<h2>最终分析报告</h2>`;
  h += `<div class="block">${(finalReport || "报告尚未生成").replace(/\n/g, "<br>")}</div>`;

  // 投资建议
  if (recommendation && recommendation !== finalReport) {
    h += `<h2>投资建议</h2><div class="block">${recommendation.replace(/\n/g, "<br>")}</div>`;
  }

  // 页脚
  h += `<div class="footer">本报告由 AlphaPilot 自动生成于 ${fmtTimestamp()}。数据仅供参考，不构成投资建议。</div>`;
  h += `</body>`;
  return h;
}

export async function downloadPDFReport(input: ReportInput): Promise<void> {
  const stockSymbol = input.stockSymbol;
  const dateStr = new Date().toISOString().split("T")[0];
  const filename = `AlphaPilot_${stockSymbol}_${dateStr}.pdf`;

  const html = _buildReportHTML(input);

  // 创建渲染容器
  const container = document.createElement("div");
  container.style.cssText = "position:fixed;left:-9999px;top:0;width:800px;background:#0d1117;z-index:-1;";
  container.innerHTML = html;
  document.body.appendChild(container);

  try {
    const { default: html2canvas } = await import("html2canvas");
    const { default: jsPDF } = await import("jspdf");

    const canvas = await html2canvas(container, {
      scale: 2,
      useCORS: true,
      backgroundColor: "#0d1117",
      logging: false,
    });

    const imgData = canvas.toDataURL("image/png");

    // A4: 595.28 x 841.89 pt
    const pdfW = 595.28;
    const pdfH = 841.89;
    const imgW = canvas.width;
    const imgH = canvas.height;

    // 每页能容纳的图像高度 (按比例)
    const pageImgH = (pdfH / pdfW) * imgW;

    const jsPdf = new jsPDF("portrait", "pt", "a4");
    let remainingH = imgH;
    let srcY = 0;
    let firstPage = true;

    while (remainingH > 0) {
      const sliceH = Math.min(pageImgH, remainingH);
      const pageCanvas = document.createElement("canvas");
      pageCanvas.width = imgW;
      pageCanvas.height = sliceH;
      const ctx = pageCanvas.getContext("2d")!;
      ctx.drawImage(canvas, 0, srcY, imgW, sliceH, 0, 0, imgW, sliceH);
      const sliceData = pageCanvas.toDataURL("image/png");

      if (!firstPage) jsPdf.addPage();
      jsPdf.addImage(sliceData, "PNG", 0, 0, pdfW, (sliceH / imgW) * pdfW);

      srcY += sliceH;
      remainingH -= sliceH;
      firstPage = false;
    }

    jsPdf.save(filename);
  } finally {
    document.body.removeChild(container);
  }
}
