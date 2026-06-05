from __future__ import annotations

import time
import json
from pathlib import Path

from evaluation.metrics import (
    EvalCase,
    EvalResult,
    EvalSuite,
    COLD_START_SYMBOLS,
    COLD_START_QUESTIONS,
    DEFAULT_EVAL_SET_PATH,
    load_eval_cases,
)


def _extract_final_text(output: dict) -> str:
    messages = output.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, dict):
        return str(last.get("content", ""))
    return str(getattr(last, "content", ""))


def _contains_forbidden_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    hits = []
    for term in terms:
        if term.lower() in lowered:
            hits.append(term)
    return hits


def run_single(symbol: str, question: str, case: EvalCase | None = None) -> EvalResult:
    result = EvalResult(
        case_id=case.case_id if case else f"{symbol}_{abs(hash(question)) % 100000}",
        symbol=symbol,
        question=question,
        expected_output_levels=case.expected_output_levels if case else [],
        should_reject=case.should_reject if case else True,
    )

    try:
        from graph.workflow import app
        from langchain_core.messages import HumanMessage
        from monitoring.counters import get_metrics

        state_in = {
            "stock_symbol": symbol,
            "messages": [HumanMessage(content=question)],
        }
        t0 = time.time()
        thread_id = f"eval_{result.case_id}_{int(t0 * 1000)}"
        output = app.invoke(
            state_in,
            config={"configurable": {"thread_id": thread_id}},
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        metrics_snapshot = get_metrics().snapshot()

        ep = output.get("evidence_packet") or {}
        guard = output.get("guard_check") or {}
        final_text = _extract_final_text(output)
        output_level = ep.get("allowed_output_level", "")

        result.output_level = output_level
        if result.expected_output_levels:
            result.output_level_match = output_level in result.expected_output_levels
        else:
            result.output_level_match = True

        hard_reject_levels = {"insufficient_evidence", "data_summary_only"}
        if output_level in hard_reject_levels or not guard.get("is_valid", False):
            result.did_reject = True

        facts = ep.get("facts", [])
        missing = ep.get("missing_fields", [])
        result.cold_start_detected = bool(ep.get("is_cold_start", False))

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
        if case:
            forbidden_hits = _contains_forbidden_terms(final_text, case.must_not_contain)
            for hit in forbidden_hits:
                hallucination_indicators.append(f"forbidden_term_detected:{hit}")
        result.hallucination_count = len(hallucination_indicators)

        result.notes = json.dumps({
            "evidence_score": ep.get("evidence_score", 0),
            "output_level": ep.get("allowed_output_level", ""),
            "cold_start": ep.get("is_cold_start", False),
            "output_level_match": result.output_level_match,
            "missing_count": len(missing),
            "elapsed_ms": elapsed_ms,
            "forbidden_terms": case.must_not_contain if case else [],
            "forbidden_hits": _contains_forbidden_terms(final_text, case.must_not_contain) if case else [],
            "metrics_snapshot": metrics_snapshot,
        })

    except (ImportError, ModuleNotFoundError) as exc:
        result.did_reject = True
        result.notes = f"environment error (missing dependency): {exc}"
    except Exception as exc:
        result.did_reject = True
        result.notes = f"pipeline error: {exc}"

    return result


def run_suite(
    eval_set_path: str | Path | None = None,
    symbols: list[str] | None = None,
    questions: list[str] | None = None,
    max_symbols: int = 5,
    max_cases: int | None = None,
    output_json_path: str | Path | None = None,
    output_summary_path: str | Path | None = None,
) -> EvalSuite:
    cases: list[EvalCase] = []
    if eval_set_path is not None:
        cases = load_eval_cases(eval_set_path)
    elif DEFAULT_EVAL_SET_PATH.exists():
        cases = load_eval_cases(DEFAULT_EVAL_SET_PATH)
    else:
        symbols = symbols or COLD_START_SYMBOLS[:max_symbols]
        questions = questions or COLD_START_QUESTIONS
        for i, sym in enumerate(symbols):
            for j, q in enumerate(questions):
                cases.append(
                    EvalCase(
                        case_id=f"generated_{i}_{j}",
                        symbol=sym,
                        question=q,
                        expected_output_levels=["insufficient_evidence", "data_summary_only", "limited_analysis"],
                        must_not_contain=["strong buy", "target price", "强烈买入", "目标价"],
                        require_traceability=True,
                    )
                )

    if max_cases is not None:
        cases = cases[:max_cases]

    suite = EvalSuite()
    total = len(cases)
    done = 0

    for case in cases:
        done += 1
        print(f"[{done}/{total}] Evaluating {case.case_id} {case.symbol}: {case.question[:40]}...")
        result = run_single(case.symbol, case.question, case=case)
        suite.add(result)
        print(
            f"  → level={result.output_level}, level_match={result.output_level_match}, "
            f"reject={result.did_reject}, hall={result.hallucination_count}, "
            f"trace={result.facts_traceable}/{result.total_conclusions}, cold_start={result.cold_start_detected}"
        )

    print("\n" + suite.summary())
    if output_json_path:
        output_path = Path(output_json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(suite.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved structured eval report to: {output_path}")
        summary_path = (
            Path(output_summary_path)
            if output_summary_path
            else output_path.with_suffix(".summary.txt")
        )
        summary_path.write_text(suite.summary() + "\n", encoding="utf-8")
        print(f"Saved eval summary to: {summary_path}")
    return suite


__all__ = ["run_single", "run_suite"]


if __name__ == "__main__":
    import sys
    eval_set = sys.argv[1] if len(sys.argv) > 1 else None
    output_json = sys.argv[2] if len(sys.argv) > 2 else "evaluation/reports/cold_start_eval_report.json"
    output_summary = sys.argv[3] if len(sys.argv) > 3 else "evaluation/reports/cold_start_eval_report.summary.txt"

    run_suite(
        eval_set_path=eval_set,
        output_json_path=output_json,
        output_summary_path=output_summary,
    )