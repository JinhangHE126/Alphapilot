LANG_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "market_title": "## Market Data Summary",
        "market_current_price": "Current Price",
        "market_source": "Source",
        "market_day_change": "1-Day Change",
        "market_rsi_oversold": "Oversold",
        "market_rsi_overbought": "Overbought",
        "market_rsi_neutral": "Neutral",
        "market_20d_vol": "20-Day Annualized Volatility",
        "market_20d_avg_vol": "20-Day Avg Volume",
        "market_shares": "shares",
        "market_cap_fallback": "Market Cap",
        "pe_ratio_fallback": "P/E Ratio",
        "market_disclaimer": "Note: Above is an automated summary of Evidence Packet facts. Not investment advice.",
        "market_not_available": "## Market Analysis: NOT AVAILABLE",
        "market_na_reason": "Reason: Evidence insufficient",
        "market_na_action": "Action: Await verified market data before technical analysis",
        "fundamental_not_available": "## Fundamental Analysis: NOT AVAILABLE",
        "fundamental_na_reason": "Reason: critical fundamental fields are missing",
        "fundamental_na_action": "Action: collect/verify fundamental data before analysis",
        "news_not_available": "## News & Sentiment Analysis: NOT AVAILABLE",
        "news_na_reason": "Reason: Evidence insufficient",
        "news_na_action": "Action: Await verified data before sentiment analysis",
        "reco_na_title": "## Personalized Recommendation: Not Available",
        "reco_na_reason": "Reason: Evidence score {score}/100, output level is {level} (full_analysis required)",
        "reco_na_action": "Action: Supplement fundamental and technical data then re-analyze",
    },
    "zh": {
        "market_title": "## 技术面数据摘要",
        "market_current_price": "当前价格",
        "market_source": "来源",
        "market_day_change": "近一日变动",
        "market_rsi_oversold": "超卖",
        "market_rsi_overbought": "超买",
        "market_rsi_neutral": "中性",
        "market_20d_vol": "20日年化波动率",
        "market_20d_avg_vol": "20日均成交量",
        "market_shares": "股",
        "market_cap_fallback": "总市值",
        "pe_ratio_fallback": "市盈率",
        "market_disclaimer": "说明：以上为 Evidence Packet 事实数据自动摘要，不构成任何投资建议。",
        "market_not_available": "## 市场分析：暂无数据",
        "market_na_reason": "原因：证据不足",
        "market_na_action": "建议：等待验证后的市场数据再进行分析",
        "fundamental_not_available": "## 基本面分析：暂无数据",
        "fundamental_na_reason": "原因：关键基本面字段缺失",
        "fundamental_na_action": "建议：获取/验证基本面数据后重新分析",
        "news_not_available": "## 新闻情绪分析：暂无数据",
        "news_na_reason": "原因：证据不足",
        "news_na_action": "建议：等待验证数据后重新分析",
        "reco_na_title": "## 个性化推荐：无法生成",
        "reco_na_reason": "原因：证据评分 {score}/100，当前分析等级为 {level}（个性化推荐需 full_analysis）",
        "reco_na_action": "建议：补充基本面和技术面数据后重新分析",
    },
    "yue": {
        "market_title": "## 技術面數據摘要",
        "market_current_price": "當前價格",
        "market_source": "來源",
        "market_day_change": "近一日變動",
        "market_rsi_oversold": "超賣",
        "market_rsi_overbought": "超買",
        "market_rsi_neutral": "中性",
        "market_20d_vol": "20日年化波動率",
        "market_20d_avg_vol": "20日均成交量",
        "market_shares": "股",
        "market_cap_fallback": "總市值",
        "pe_ratio_fallback": "市盈率",
        "market_disclaimer": "說明：以上係 Evidence Packet 事實數據自動摘要，不構成任何投資建議。",
        "market_not_available": "## 市場分析：暫無數據",
        "market_na_reason": "原因：證據不足",
        "market_na_action": "建議：等驗證咗嘅市場數據返嚟先做技術分析",
        "fundamental_not_available": "## 基本面分析：暫無數據",
        "fundamental_na_reason": "原因：關鍵基本面欄位缺失",
        "fundamental_na_action": "建議：攞到/驗證基本面數據後重新分析",
        "news_not_available": "## 新聞情緒分析：暫無數據",
        "news_na_reason": "原因：證據不足",
        "news_na_action": "建議：等驗證數據後重新分析",
        "reco_na_title": "## 個人化推薦：無法生成",
        "reco_na_reason": "原因：證據評分 {score}/100，當前分析等級為 {level}（個人化推薦需 full_analysis）",
        "reco_na_action": "建議：補充基本面同技術面數據後重新分析",
    },
}


def get_label(key: str, language: str) -> str:
    labels = LANG_TRANSLATIONS.get(language, LANG_TRANSLATIONS["en"])
    return labels.get(key, LANG_TRANSLATIONS["en"].get(key, key))


_LANG_INSTRUCTION: dict[str, str] = {
    "zh": "你必须全程使用简体中文回复。所有分析内容、指标解读、结论、建议都必须使用简体中文输出。",
    "yue": "你必须全程使用粤语 (Cantonese) 回复。所有分析内容、指标解读、结论、建议都必须使用粤语输出。禁止使用其他语言。",
}


def inject_language(state: dict, language: str) -> None:
    if not language or language == "en":
        return
    instruction = _LANG_INSTRUCTION.get(language)
    if not instruction:
        return
    messages = state.get("messages", [])
    messages.insert(0, {"role": "system", "content": instruction})