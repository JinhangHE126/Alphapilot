from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.metrics import DEFAULT_EVAL_SET_PATH, load_eval_cases  # noqa: E402


def test_eval_dataset_loads():
    cases = load_eval_cases(DEFAULT_EVAL_SET_PATH)
    assert len(cases) >= 30
    assert all(c.case_id for c in cases)
    assert all(c.symbol for c in cases)
    assert all(c.question for c in cases)

