from __future__ import annotations

import time
import json

from evaluation.metrics import (
    EvalResult,
    EvalSuite,
    COLD_START_SYMBOLS,
    COLD_START_QUESTIONS,
)


def run_single(symbol: str, question: str) -> EvalResult:
    result = EvalResult(
        symbol=symbol,
        question=question,
        should_reject=True,
    )

    try:
        from graph.workflow import app
        from langchain_core.messages import HumanMessage

        state_in = {
            "stock_symbol": symbol,
            "messages": [HumanMessage(content=question)],
        }
        t0 = time.time()
        output = app.invoke(state_in)
        elapsed_ms = int((time.time() - t0) * 1000)

        ep = output.get("evidence_packet") or {}
        guard = output.get("guard_check") or {}

        if not guard.get("is_valid", False):
            result.did_reject = True

        facts = ep.get("facts", [])
        missing = ep.get("missing_fields", [])

        result.total_conclusions = len(facts) if facts else 1
        traceable = sum(
            1 for f in facts
            if f.get("source") and f.get("source") != "init"
            and f.get("confidence_tier") != "llm_inferred"
        )
        result.facts_traceable = traceable

        hallucination_indicators = []
        if guard.get("issues"):
            if isinstance(guard["issues"], list):
                hallucination_indicators.extend(guard["issues"])
        result.hallucination_count = len(hallucination_indicators)

        result.notes = json.dumps({
            "evidence_score": ep.get("evidence_score", 0),
            "output_level": ep.get("allowed_output_level", ""),
            "cold_start": ep.get("is_cold_start", False),
            "missing_count": len(missing),
            "elapsed_ms": elapsed_ms,
        })

    except Exception as exc:
        result.did_reject = True
        result.notes = f"pipeline error: {exc}"

    return result


def run_suite(
    symbols: list[str] | None = None,
    questions: list[str] | None = None,
    max_symbols: int = 5,
) -> EvalSuite:
    symbols = symbols or COLD_START_SYMBOLS[:max_symbols]
    questions = questions or COLD_START_QUESTIONS

    suite = EvalSuite()
    total = len(symbols) * len(questions)
    done = 0

    for sym in symbols:
        for q in questions:
            done += 1
            print(f"[{done}/{total}] Evaluating {sym}: {q[:40]}...")
            result = run_single(sym, q)
            suite.add(result)
            print(f"  → reject={result.did_reject}, hall={result.hallucination_count}, "
                  f"trace={result.facts_traceable}/{result.total_conclusions}")

    print("\n" + suite.summary())
    return suite


__all__ = ["run_single", "run_suite"]