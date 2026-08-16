# AI Incident Response (Demo)

> AlphaPilot demonstrates engineering controls aligned with selected SFC regulatory expectations. This document is part of a technical demonstration and does not constitute legal advice, SFC certification, regulatory approval, or a determination of compliance.

## Scope

- Covers AI-governance incidents in AlphaPilot demo workflows (analysis, approval, publication).
- This is an operational demo procedure, not a formally approved enterprise IR plan.

## Incident Categories

| Severity | Example | Immediate Action |
| --- | --- | --- |
| High | Unauthorized publish, systemic unsupported claims, sensitive data exposure | Activate kill switch, stop publication, preserve audit evidence, notify owners |
| Medium | Repeated model/provider failures, elevated guard blocking issues | Switch to degraded mode, investigate provider path, monitor audit risk flags |
| Low | Non-blocking data quality mismatch or UI presentation issue | Log issue, schedule remediation, track in backlog |

## Response Workflow

1. Detect signal (guard failures, risk flags, user report, test failure).
2. Contain impact (`AI_OUTPUT_ENABLED=false` and/or `AI_PUBLICATION_ENABLED=false`).
3. Preserve evidence (request ID, audit record, export snapshot, logs).
4. Triage root cause (provider failure, prompt abuse, logic regression, data source issue).
5. Remediate and re-test affected controls.
6. Resume only after explicit reviewer approval and verification checks.

## Evidence to Capture

- Request IDs and associated `ai_audit_records`.
- Approval transition history and reviewer comments.
- Guard and claim-validation outcomes.
- Relevant API logs and test outputs.

## Open Items

- Final on-call roster and escalation matrix are pending.
- SLA/SLO targets for containment and recovery are not defined for demo.
