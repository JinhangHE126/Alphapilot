"""上传文档敏感信息扫描与打码。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

REDACTED = "[REDACTED]"

# 中国大陆身份证号（18 位，末位可为 X）
_CN_ID: Pattern[str] = re.compile(
    r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
)
# 银行卡号（16–19 位，前后非数字）
_BANK_CARD: Pattern[str] = re.compile(r"(?<!\d)(?:\d[ -]?){15,18}\d(?!\d)")
# 电话（含 +86、区号、手机号）
_PHONE: Pattern[str] = re.compile(
    r"(?:\+?86[-\s]?)?(?:0\d{2,3}[-\s]?)?1[3-9]\d{9}\b"
    r"|(?:\+?86[-\s]?)?0\d{2,3}[-\s]?\d{7,8}\b"
)
# 邮箱
_EMAIL: Pattern[str] = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

_PATTERNS: list[tuple[str, Pattern[str]]] = [
    ("cn_id", _CN_ID),
    ("bank_card", _BANK_CARD),
    ("phone", _PHONE),
    ("email", _EMAIL),
]


@dataclass
class ScanResult:
    text: str
    redacted: bool = False
    hits: list[str] = field(default_factory=list)


def scan(text: str) -> ScanResult:
    """
    扫描并打码敏感信息。命中项替换为 [REDACTED]。
    返回打码后文本及命中类型列表。
    """
    if not text:
        return ScanResult(text=text, redacted=False, hits=[])

    redacted_text = text
    hits: list[str] = []
    for label, pattern in _PATTERNS:
        if pattern.search(redacted_text):
            hits.append(label)
            redacted_text = pattern.sub(REDACTED, redacted_text)

    return ScanResult(
        text=redacted_text,
        redacted=bool(hits),
        hits=hits,
    )
