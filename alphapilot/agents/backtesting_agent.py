import numpy as np
from config.llm import get_llm
from tools.data_collector import fetch_price_history


def _compute_backtest_metrics(close_prices, benchmark_close=None):
    returns = close_prices.pct_change().dropna()
    if len(returns) < 20:
        return None

    total_return = float((close_prices.iloc[-1] / close_prices.iloc[0] - 1) * 100)
    ann_return = float(((1 + total_return / 100) ** (252 / len(returns)) - 1) * 100)
    ann_vol = float(returns.std() * np.sqrt(252) * 100)
    sharpe = round(ann_return / ann_vol, 2) if ann_vol > 0 else 0.0

    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_dd = float(drawdown.min() * 100)

    win_rate = float((returns > 0).sum() / len(returns) * 100)

    return {
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(ann_return, 2),
        "annualized_volatility_pct": round(ann_vol, 2),
        "sharpe_ratio": sharpe,
        "max_drawdown_pct": round(max_dd, 2),
        "win_rate_pct": round(win_rate, 2),
        "data_points": len(returns),
    }


def backtesting_agent(state):
    """
    Backtesting Agent - v4 程序化计算版
    回测指标由 Python 确定性计算，LLM 仅做文字解读。
    """
    ep = state.get("evidence_packet", {})
    ep_score = int(ep.get("evidence_score", 0)) if ep else 0
    symbol = state.get("stock_symbol", "")
    language = state.get("language", "")

    def _t(key_en, key_zh, key_yue):
        if language == "zh":
            return {"en": key_en, "zh": key_zh, "yue": key_yue}.get(language, key_en)
        if language == "yue":
            return {"en": key_en, "zh": key_zh, "yue": key_yue}.get(language, key_en)
        return key_en

    if ep_score < 50:
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    f"## {_t('Backtesting Report: NOT AVAILABLE', '回测报告：暂不可用', '回測報告：暫不可用')}\n"
                    f"- {_t('Reason', '原因', '原因')}: {_t(f'Evidence score {ep_score}/100 insufficient for backtesting', f'证据评分为 {ep_score}/100，不满足回测最低要求', f'證據評分為 {ep_score}/100，唔滿足回測最低要求')}\n"
                    f"- {_t('Required: evidence_score >= 50', '最低要求: evidence_score >= 50', '最低要求: evidence_score >= 50')}"
                ),
            }],
        }

    try:
        df, err = fetch_price_history(symbol)
    except Exception:
        df, err = None, "exception"

    if df is None or df.empty or len(df) < 20:
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    f"## {_t('Backtesting Report: NOT AVAILABLE', '回测报告：暂不可用', '回測報告：暫不可用')}\n"
                    f"- {_t(f'Reason: Insufficient price data for {symbol}', f'原因：{symbol} 价格数据不足', f'原因：{symbol} 價格數據不足')}\n"
                    f"- {_t('Required: 20+ trading days of OHLCV data', '最低要求: 至少20个交易日的OHLCV数据', '最低要求: 最少20個交易日嘅OHLCV數據')}"
                ),
            }],
        }

    import pandas as pd
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()

    metrics = _compute_backtest_metrics(close)
    if metrics is None:
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    f"## {_t('Backtesting Report: NOT AVAILABLE', '回测报告：暂不可用', '回測報告：暫不可用')}\n"
                    f"- {_t(f'Reason: Insufficient valid returns for {symbol}', f'原因：{symbol} 有效收益率数据不足', f'原因：{symbol} 有效收益率數據不足')}\n"
                    f"- {_t('Required: 20+ valid daily returns', '最低要求: 至少20个有效日收益率', '最低要求: 最少20個有效日收益率')}"
                ),
            }],
        }

    metrics_text = (
        f"- Total Return: {metrics['total_return_pct']}%\n"
        f"- Annualized Return: {metrics['annualized_return_pct']}%\n"
        f"- Annualized Volatility: {metrics['annualized_volatility_pct']}%\n"
        f"- Sharpe Ratio: {metrics['sharpe_ratio']}\n"
        f"- Max Drawdown: {metrics['max_drawdown_pct']}%\n"
        f"- Win Rate: {metrics['win_rate_pct']}%\n"
        f"- Data Points: {metrics['data_points']} trading days"
    )

    lang_instruction = ""
    if language and language != "en":
        label_map = {"zh": "简体中文", "yue": "粤语 (Cantonese)"}
        label = label_map.get(language, language)
        lang_instruction = (
            f"\n\n[语言要求] 请全程使用 {label} 回复。"
            f"所有报告内容、指标解读、评论都必须用 {label} 输出。\n"
        )

    llm = get_llm("backtesting")
    prompt = (
        f"You are a backtesting report writer. Below are PROGRAMMATICALLY COMPUTED metrics for {symbol}. "
        f"Do NOT recalculate or change any numbers. Write a concise report interpreting these results.\n\n"
        f"{metrics_text}\n\n"
        f"Output a structured backtesting report with these exact numbers, "
        f"adding brief commentary on what each metric means for a trader. "
        f"Do NOT invent additional metrics or make investment recommendations."
        f"{lang_instruction}"
    )

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
    except Exception:
        content = f"## Backtesting Report: {symbol}\n\n{metrics_text}\n\n*(LLM commentary unavailable)*"

    return {"messages": [{"role": "assistant", "content": content}]}