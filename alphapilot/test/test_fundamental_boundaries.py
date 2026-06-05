from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.fundamental_agent import fundamental_agent  # noqa: E402


def test_fundamental_not_available_when_evidence_insufficient():
    state = {
        "evidence_packet": {
            "allowed_output_level": "insufficient_evidence",
            "facts": [],
        },
        "messages": [{"role": "user", "content": "analyze fundamentals"}],
    }
    out = fundamental_agent(state)
    msg = out["messages"][-1]["content"]
    assert "Fundamental Analysis: NOT AVAILABLE" in msg


def test_fundamental_not_available_when_critical_fields_all_missing():
    state = {
        "evidence_packet": {
            "allowed_output_level": "full_analysis",
            "facts": [{"field": "news_headline", "value": "headline"}],
        },
        "messages": [{"role": "user", "content": "analyze fundamentals"}],
    }
    out = fundamental_agent(state)
    msg = out["messages"][-1]["content"]
    assert "critical fundamental fields are missing" in msg
