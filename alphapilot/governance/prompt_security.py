"""Prompt injection, secret, and sensitive-input checks before agent execution.

Regex/heuristic demo controls — not a complete attack detector.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from knowledge.sensitive_scanner import scan as sensitive_scan


@dataclass
class PromptSecurityResult:
    allowed: bool
    sanitized_text: str
    risk_flags: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)


_SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "OPENAI_API_KEY": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "AWS_ACCESS_KEY": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "BEARER_TOKEN": re.compile(
        r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}",
        re.IGNORECASE,
    ),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
}


_INJECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "INSTRUCTION_OVERRIDE": re.compile(
        r"ignore (?:all |any )?(?:previous|prior|above) instructions",
        re.IGNORECASE,
    ),
    "SYSTEM_PROMPT_EXFILTRATION": re.compile(
        r"(reveal|show|print|return).{0,30}(system prompt|developer message)",
        re.IGNORECASE,
    ),
    "POLICY_BYPASS": re.compile(
        r"(bypass|disable|ignore).{0,30}(guard|policy|citation|safety)",
        re.IGNORECASE,
    ),
    "ROLE_OVERRIDE": re.compile(
        r"(you are now|act as if).{0,30}(no restrictions|unrestricted|developer)",
        re.IGNORECASE,
    ),
}


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def scan_prompt(text: str) -> PromptSecurityResult:
    """
    Scan user input for secrets, PII and prompt-injection patterns.

    - Secrets / injection patterns -> block request.
    - PII -> redact and allow.
    """
    raw = text or ""
    risk_flags: list[str] = []
    blocked_reasons: list[str] = []

    for code, pattern in _SECRET_PATTERNS.items():
        if pattern.search(raw):
            risk_flags.extend(["SECRET_DETECTED", code])
            blocked_reasons.append(code)

    for code, pattern in _INJECTION_PATTERNS.items():
        if pattern.search(raw):
            risk_flags.extend(["PROMPT_INJECTION", code])
            blocked_reasons.append(code)

    pii = sensitive_scan(raw)
    if pii.redacted:
        risk_flags.append("PII_REDACTED")
        for hit in pii.hits:
            risk_flags.append(f"PII_{str(hit).upper()}")

    risk_flags = _dedupe(risk_flags)
    blocked_reasons = _dedupe(blocked_reasons)
    return PromptSecurityResult(
        allowed=len(blocked_reasons) == 0,
        sanitized_text=pii.text,
        risk_flags=risk_flags,
        blocked_reasons=blocked_reasons,
    )


__all__ = ["PromptSecurityResult", "scan_prompt"]
