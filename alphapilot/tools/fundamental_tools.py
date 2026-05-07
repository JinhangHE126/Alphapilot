import os
import json
import re
from pathlib import Path
from config.proxy import get_requests_proxies
import fitz  # PyMuPDF
import requests
from pydantic import BaseModel, Field
from typing import List
from rag.vectorstore import rag
from config.llm import get_llm


# model = get_llm("fundamental")

class FundamentalData(BaseModel):
    """Structured financial report data (Revenue, EPS, Margin, etc. required in the proposal)"""
    symbol: str = Field(description="Stock ticker")
    revenue_growth: float = Field(description="Year-over-year revenue growth (%)")
    eps_growth: float = Field(description="Year-over-year EPS growth (%)")
    gross_margin: float = Field(description="Gross margin (%)")
    net_margin: float = Field(description="Net margin (%)")
    key_points: List[str] = Field(description="Key highlights or risk factors")
    summary: str = Field(description="One-sentence summary")


def _extract_json_text(text: str) -> str:
    markdown_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if markdown_block:
        return markdown_block.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    raise ValueError("LLM response does not contain valid JSON content.")


def _open_pdf(pdf_path: str):
    if pdf_path.startswith(("http://", "https://")):
        response = requests.get(
            pdf_path,
            proxies=get_requests_proxies("fundamental"),
            timeout=30,
        )
        response.raise_for_status()
        return fitz.open(stream=response.content, filetype="pdf")

    return fitz.open(pdf_path)


def _extract_pdf_reference(text: str) -> str:
    """Extract a PDF URL or local PDF path from free-form text."""
    if not text:
        return ""

    # Prefer HTTP(S) PDF URL when present.
    url_match = re.search(r"https?://[^\s'\"<>]+\.pdf(?:\?[^\s'\"<>]*)?", text, re.IGNORECASE)
    if url_match:
        return url_match.group(0)

    # Fallback to local paths ending with .pdf (absolute/relative, with possible spaces).
    path_match = re.search(
        r"(?:\.{1,2}/|/)?[^\n\r\t\"']*?\.pdf",
        text,
        re.IGNORECASE,
    )
    if path_match:
        return path_match.group(0).strip()

    return ""


def _resolve_pdf_path(symbol: str, user_query: str = "") -> str:
    """Resolve PDF path from query first, then from local reports by symbol."""
    candidate = _extract_pdf_reference(user_query)
    if candidate:
        if candidate.startswith(("http://", "https://")):
            return candidate
        path_obj = Path(candidate).expanduser()
        if path_obj.exists():
            return str(path_obj)

    reports_dir = Path(__file__).resolve().parents[1] / "data" / "reports"
    if not reports_dir.exists():
        raise ValueError(
            "No PDF found in query, and local reports directory does not exist: "
            f"{reports_dir}"
        )

    patterns = [
        f"{symbol}*.pdf",
        f"{symbol.upper()}*.pdf",
        f"*{symbol}*.pdf",
        f"*{symbol.upper()}*.pdf",
    ]
    for pattern in patterns:
        matches = sorted(reports_dir.glob(pattern))
        if matches:
            return str(matches[0])

    raise ValueError(
        f"Unable to locate a PDF for symbol '{symbol}'. "
        "Provide a PDF URL/local path in your request, or add a report under data/reports/."
    )


def parse_financial_pdf(pdf_path: str, symbol: str, model=None) -> FundamentalData:
    """
    Parse a financial report PDF and return structured data.「解析财务报告 PDF 文件并返回结构化数据。」
    (Currently uses an LLM-assisted parser; real projects can replace it with more precise rule-based extraction.)
    """
    try:
        # 读取 PDF 文本
        doc = _open_pdf(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()

        # 使用 LLM 提取结构化数据（推荐方式）
        if model is None:
            from config.llm import get_llm
            model = get_llm("fundamental")
        # llm = model
        
        prompt = f"""
        Extract structured information from the following financial report text. The stock ticker is {symbol}.
        Return JSON only, strictly following this Pydantic schema:
        {FundamentalData.model_json_schema()}

        Financial report text:
        {full_text[:8000]}  # Limit length to avoid exceeding the token limit
        """

        response = model.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)
        if isinstance(response_text, list):
            response_text = "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in response_text
            )

        json_text = _extract_json_text(str(response_text))
        payload = json.loads(json_text)
        payload["symbol"] = payload.get("symbol") or symbol
        return FundamentalData.model_validate(payload)
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")


def analyze_fundamental_request(symbol: str, user_query: str = "", model=None) -> FundamentalData:
    """
    Smart entrypoint for agents:
    1) parse URL/local PDF path from user query
    2) fallback to data/reports/{symbol}*.pdf
    3) run structured PDF parsing
    """
    resolved_pdf = _resolve_pdf_path(symbol=symbol, user_query=user_query)
    return parse_financial_pdf(pdf_path=resolved_pdf, symbol=symbol)





def retrieve_financial_context(symbol: str, query: str) -> str:
    """Retrieve relevant financial information from RAG"""
    context = rag.query(f"{symbol} {query}")
    if context:
        return "\n\n".join(context)
    return "No relevant historical financial reports found."