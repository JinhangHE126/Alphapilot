from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.alert_agent import alert_agent  # noqa: E402


def test_alert_not_available_when_evidence_insufficient():
    state = {
        "evidence_packet": {
            "allowed_output_level": "insufficient_evidence",
            "facts": [],
        },
        "messages": [{"role": "user", "content": "monitor TSLA and alert me"}],
    }
    out = alert_agent(state)
    msg = out["messages"][-1]["content"]
    assert "Alert Analysis: NOT AVAILABLE" in msg

