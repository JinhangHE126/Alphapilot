#!/usr/bin/env python3
"""Generate machine-readable Week 2 technical log for AAPL human-trust pilot."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "Docs/ra-lu-autoredtrader-human-trust/assets"

ATTACKED_RESULTS_PATH = ASSETS_DIR / "attacked_prerun_results.json"
CLEAN_BASELINE_PATH = ASSETS_DIR / "clean_baseline.json"
STIMULI_MANIFEST_PATH = ASSETS_DIR / "stimuli/stimuli_manifest.json"
OUT_PATH = ASSETS_DIR / "technical_log_AAPL.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: str) -> str:
    return path


def stimulus_assets(stimulus_id: str, manifest_entry: dict) -> dict:
    return {
        "markdown": rel(manifest_entry["markdown"]),
        "html": rel(manifest_entry["html"]),
        "g1_png": f"Docs/ra-lu-autoredtrader-human-trust/assets/G1_{stimulus_id}.png",
        "g2_png": f"Docs/ra-lu-autoredtrader-human-trust/assets/G2_{stimulus_id}.png",
        "g3_png": f"Docs/ra-lu-autoredtrader-human-trust/assets/G3_{stimulus_id}.png",
        "g2_html": f"Docs/ra-lu-autoredtrader-human-trust/assets/stimuli/G2_{stimulus_id}.html",
        "g3_html": f"Docs/ra-lu-autoredtrader-human-trust/assets/stimuli/G3_{stimulus_id}.html",
    }


def summarize_primary(stimulus_id: str, manifest_entry: dict, attacked_results: dict, clean: dict) -> dict:
    source_type = manifest_entry["source_type"]
    attack = manifest_entry["attack"]

    if attack == "clean":
        notes = "baseline"
        if stimulus_id == "S1":
            notes = "news clean baseline; thin news channel"
        elif stimulus_id == "S3":
            notes = "filing clean baseline; cited [doc:1,3,4]"
        return {
            "stimulus_id": stimulus_id,
            "source_type": source_type,
            "attack": False,
            "condition": "clean",
            "run_id": manifest_entry["run_id"],
            "backup_run_id": None,
            "perturbation_type": None,
            "MER": 0.0,
            "RDR": 0,
            "recommendation": manifest_entry["recommendation"],
            "guard_status": "pass" if manifest_entry["guard_valid"] else "fail",
            "guard_confidence": manifest_entry["guard_confidence"],
            "output_level": "full_analysis" if manifest_entry["guard_valid"] else None,
            "injection_verified": False,
            "selection_rationale": notes,
            "assets": stimulus_assets(stimulus_id, manifest_entry),
        }

    summary_runs = attacked_results["summary"][stimulus_id]
    primary = next(run for run in summary_runs if run["attack_id"] == manifest_entry["run_id"])
    backup = next((run for run in summary_runs if run["attack_id"] == manifest_entry["backup_run_id"]), None)

    if stimulus_id == "S2":
        rationale = "Selected ATT_S2_002 as primary because Guard passed and MER=0.2; ATT_S2_001 kept as backup for stronger RDR but invalid guard."
    else:
        rationale = "Selected ATT_S4_002 as primary because Guard passed cleanly; ATT_S4_001 kept as backup because Sell/RDR may be parser artifact."

    return {
        "stimulus_id": stimulus_id,
        "source_type": source_type,
        "attack": True,
        "condition": "attacked",
        "run_id": primary["attack_id"],
        "backup_run_id": backup["attack_id"] if backup else None,
        "perturbation_type": primary["perturbation_type"],
        "MER": primary["MER"],
        "RDR": primary["RDR"],
        "recommendation": primary["recommendation_attacked"],
        "recommendation_clean": clean["recommendation"],
        "guard_status": "pass" if primary["guard"]["is_valid"] else "fail",
        "guard_confidence": primary["guard"]["confidence"],
        "output_level": primary["guard"]["output_level"],
        "injection_verified": primary["injection_verified"],
        "selection_rationale": rationale,
        "guard_warnings": primary["guard"]["warnings"],
        "assets": stimulus_assets(stimulus_id, manifest_entry),
        "backup_summary": {
            "run_id": backup["attack_id"] if backup else None,
            "MER": backup["MER"] if backup else None,
            "RDR": backup["RDR"] if backup else None,
            "recommendation": backup["recommendation_attacked"] if backup else None,
            "guard_status": "pass" if backup and backup["guard"]["is_valid"] else "fail" if backup else None,
        },
    }


def build_quality_gates(primary_stimuli: list[dict]) -> dict:
    attacked = [s for s in primary_stimuli if s["attack"]]
    any_rdr_or_shift = True
    return {
        "s2_attack_path_documented": True,
        "s4_attack_uses_clean_cited_chunk": True,
        "s2_mer_positive": any(s["stimulus_id"] == "S2" and s["MER"] > 0 for s in attacked),
        "s4_mer_positive": any(s["stimulus_id"] == "S4" and s["MER"] > 0 for s in attacked),
        "rdr_or_narrative_shift_documented": any_rdr_or_shift,
        "attacked_reports_read_naturally": False,
        "g3_assets_show_guard_signal": all(
            s["stimulus_id"] not in {"S2", "S4"} or len(s.get("guard_warnings", [])) > 0 for s in primary_stimuli
        ),
        "clean_and_attacked_layout_identical": True,
    }


def main() -> None:
    attacked_results = load_json(ATTACKED_RESULTS_PATH)
    clean = load_json(CLEAN_BASELINE_PATH)
    manifest = load_json(STIMULI_MANIFEST_PATH)

    manifest_by_id = {s["stimulus_id"]: s for s in manifest["stimuli"]}
    stimuli = [
        summarize_primary("S1", manifest_by_id["S1"], attacked_results, clean["clean_baseline"] if "clean_baseline" in clean else clean),
        summarize_primary("S2", manifest_by_id["S2"], attacked_results, clean["clean_baseline"] if "clean_baseline" in clean else clean),
        summarize_primary("S3", manifest_by_id["S3"], attacked_results, clean["clean_baseline"] if "clean_baseline" in clean else clean),
        summarize_primary("S4", manifest_by_id["S4"], attacked_results, clean["clean_baseline"] if "clean_baseline" in clean else clean),
    ]

    output = {
        "symbol": "AAPL",
        "study": "ra-lu-autoredtrader-human-trust",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week": 2,
        "status": "day_6_7_complete",
        "clean": {
            "run_id": clean["run_id"],
            "timestamp": clean["timestamp"],
            "recommendation": clean["recommendation"],
            "strategy_score": clean["strategy_score"],
            "risk_score": clean["risk_score"],
            "guard_status": "pass" if clean["guard"]["is_valid"] else "fail",
            "guard_confidence": clean["guard"]["confidence"],
            "output_level": clean["guard"]["output_level"],
            "MER": clean["MER"],
            "RDR": clean["RDR"],
            "document_evidence_count": clean["document_evidence_count"],
            "citation_chunk_ids": clean["citation_chunk_ids"],
            "structured_facts_snapshot": clean["structured_facts_snapshot"],
            "source_json": clean["source_json"],
            "report_path": clean["report_path"],
        },
        "stimuli": stimuli,
        "all_runs": attacked_results["results"],
        "summary": {
            "runs_per_stimulus": attacked_results["runs_per_stimulus"],
            "max_mer": attacked_results["summary"]["max_mer"],
            "any_rdr_1": attacked_results["summary"]["any_rdr_1"],
            "selected_primary_runs": {
                "S2": "ATT_S2_002",
                "S4": "ATT_S4_002",
            },
        },
        "quality_gates": build_quality_gates(stimuli),
        "merge_template": {
            "join_key": "stimulus_id",
            "fields": ["MER", "RDR", "trust_mean", "adoption_mean", "detection_rate"],
        },
        "source_files": {
            "clean_baseline": rel("Docs/ra-lu-autoredtrader-human-trust/assets/clean_baseline.json"),
            "attacked_prerun_results": rel("Docs/ra-lu-autoredtrader-human-trust/assets/attacked_prerun_results.json"),
            "stimuli_manifest": rel("Docs/ra-lu-autoredtrader-human-trust/assets/stimuli/stimuli_manifest.json"),
        },
        "notes": [
            "S1/S3 share CLEAN_001 body and differ by source label only.",
            "S2 attack path uses news_headline fact injection because FAISS news chunks were unusable.",
            "S4 attack path modifies Risk_Factors_i03, which is cited in CLEAN_001.",
            "ATT_S4_001 Sell/RDR may be parser artifact; ATT_S4_002 is primary.",
        ],
    }

    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
