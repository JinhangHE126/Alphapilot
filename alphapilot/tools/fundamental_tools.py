import os
import json
import re

import fitz  # PyMuPDF
from pydantic import BaseModel, Field
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI

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


def parse_financial_pdf(pdf_path: str, symbol: str) -> FundamentalData:
    """
    Parse a financial report PDF and return structured data.「解析财务报告 PDF 文件并返回结构化数据。」
    (Currently uses an LLM-assisted parser; real projects can replace it with more precise rule-based extraction.)
    """
    try:
        # 读取 PDF 文本
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()

        # 使用 LLM 提取结构化数据（推荐方式）
        llm = ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite-preview"),
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )
        # llm = ChatOpenAI(model="gpt-4o", temperature=0)
        prompt = f"""
        Extract structured information from the following financial report text. The stock ticker is {symbol}.
        Return JSON only, strictly following this Pydantic schema:
        {FundamentalData.model_json_schema()}

        Financial report text:
        {full_text[:8000]}  # Limit length to avoid exceeding the token limit
        """

        response = llm.invoke(prompt)
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