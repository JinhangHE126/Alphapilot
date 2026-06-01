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


def _extract_page_tables(page, page_number: int) -> list[dict]:
    """Try structured table extraction via fitz.Table before LLM fallback."""
    try:
        tables = page.find_tables()
    except Exception:
        return []

    results = []
    for table in tables:
        try:
            df = table.to_pandas()
        except Exception:
            continue
        if df is None or df.empty:
            continue
        results.append({
            "page_number": page_number,
            "columns": [str(c) for c in df.columns],
            "rows": df.head(50).fillna("").to_dict(orient="records"),
        })
    return results


def _validate_revenue_boundary(facts_dict: dict, prior_revenue: float | None = None) -> list[str]:
    """Validate revenue/gross_profit values against ±80% boundary from prior quarter."""
    warnings = []
    revenue = facts_dict.get("revenue_growth")
    if revenue is not None and prior_revenue is not None and prior_revenue > 0:
        change_pct = abs(revenue - prior_revenue) / prior_revenue
        if change_pct > 0.8:
            warnings.append(
                f"⚠️ revenue_growth={revenue} deviates {change_pct:.0%} from prior ({prior_revenue}), "
                f"exceeds ±80% boundary — flagged suspicious"
            )
    gross_margin = facts_dict.get("gross_margin")
    if gross_margin is not None and (gross_margin < -20 or gross_margin > 95):
        warnings.append(
            f"⚠️ gross_margin={gross_margin}% outside reasonable range [-20, 95] — flagged suspicious"
        )
    net_margin = facts_dict.get("net_margin")
    if net_margin is not None and (net_margin < -50 or net_margin > 80):
        warnings.append(
            f"⚠️ net_margin={net_margin}% outside reasonable range [-50, 80] — flagged suspicious"
        )
    return warnings


def parse_financial_pdf(pdf_path: str, symbol: str, model=None) -> FundamentalData:
    """
    Parse a financial report PDF with per-page extraction, table-first strategy,
    page-number citations, and boundary validation (±80% revenue check).
    "解析财务报告 PDF 文件并返回结构化数据。"
    """
    try:
        doc = _open_pdf(pdf_path)
        if model is None:
            from config.llm import get_llm
            model = get_llm("fundamental")

        all_table_data = []
        page_texts = []
        total_pages = len(doc)

        for page_num, page in enumerate(doc, 1):
            tables = _extract_page_tables(page, page_num)
            if tables:
                all_table_data.extend(tables)

            text = page.get_text()
            if text.strip():
                page_texts.append(f"--- PAGE {page_num}/{total_pages} ---\n{text}")

        doc.close()

        table_context = ""
        if all_table_data:
            table_lines = ["### Structured Table Data (fitz.Table extraction):"]
            for t in all_table_data[:8]:
                table_lines.append(f"  [Page {t['page_number']}] Columns: {', '.join(t['columns'][:10])}")
                for row in t["rows"][:6]:
                    table_lines.append(f"    {row}")
            table_context = "\n".join(table_lines)

        combined_text = "\n\n".join(page_texts)
        if len(combined_text) > 12000:
            combined_text = combined_text[:6000] + "\n\n...(middle pages omitted)...\n\n" + combined_text[-6000:]

        prompt = f"""
Extract structured financial information for {symbol} from the report below.
The report has {total_pages} pages. Each section is prefixed with its page number.
{table_context}

Return JSON only, strictly following this Pydantic schema:
{FundamentalData.model_json_schema()}

IMPORTANT:
- Cite the PAGE number where each value was found in key_points (e.g., "[p.5] revenue_growth=12.3%")
- Prefer values from structured tables over narrative text when both available.
- If a value cannot be determined, omit the field rather than guessing.

Report text (page-prefixed):
{combined_text}
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

        boundary_warnings = _validate_revenue_boundary(payload)
        if boundary_warnings:
            existing = payload.get("key_points", []) or []
            payload["key_points"] = existing + boundary_warnings

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