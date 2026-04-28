from pathlib import Path
import sys
import tempfile
import json

import fitz


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import fundamental_tools


class MockResponse:
    def __init__(self, content):
        self.content = content


class MockLLM:
    response_mode = "plain_json"

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def _build_payload(self):
        return {
            "revenue_growth": 15.2,
            "eps_growth": 8.7,
            "gross_margin": 42.3,
            "net_margin": 18.5,
            "key_points": [
                "Revenue exceeded expectations",
                "Gross margin improved",
                "Operating expenses were well controlled",
                "Cash flow remained strong",
            ],
            "summary": "The latest report indicates resilient growth and healthy profitability.",
        }

    def invoke(self, prompt: str):
        print("=== prompt preview ===")
        print(prompt[:500])
        payload = self._build_payload()

        if self.response_mode == "plain_json":
            payload["symbol"] = "TSLA"
            return MockResponse(json.dumps(payload))

        if self.response_mode == "markdown_json":
            # Intentionally do not return symbol to test fallback logic.
            return MockResponse(f"```json\n{json.dumps(payload, indent=2)}\n```")

        if self.response_mode == "invalid":
            return MockResponse("No JSON in this response.")

        return MockResponse(json.dumps(payload))


def create_sample_pdf(pdf_path: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "TSLA Q4 financial report\n"
        "Revenue increased 15.2% year over year.\n"
        "EPS increased 8.7% year over year.\n"
        "Gross margin was 42.3%, and net margin was 18.5%.\n",
    )
    doc.save(pdf_path)
    doc.close()


def run_case(case_name: str, symbol: str, response_mode: str) -> None:
    MockLLM.response_mode = response_mode
    fundamental_tools.ChatGoogleGenerativeAI = MockLLM

    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        create_sample_pdf(tmp.name)
        result = fundamental_tools.parse_financial_pdf(tmp.name, symbol)

    print(f"=== {case_name} output ===")
    print(result.model_dump())


def run_invalid_case(symbol: str) -> None:
    MockLLM.response_mode = "invalid"
    fundamental_tools.ChatGoogleGenerativeAI = MockLLM

    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        create_sample_pdf(tmp.name)
        try:
            fundamental_tools.parse_financial_pdf(tmp.name, symbol)
            raise AssertionError("Expected ValueError was not raised for invalid JSON response.")
        except ValueError as exc:
            print("=== invalid response case ===")
            print(str(exc))


def main():
    run_case("plain JSON case", "TSLA", "plain_json")
    run_case("markdown JSON case (symbol fallback)", "AAPL", "markdown_json")
    run_invalid_case("MSFT")


if __name__ == "__main__":
    main()