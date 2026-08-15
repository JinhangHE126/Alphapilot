# SFC-Aligned Control Mapping (Demo)

## Scope Statement

- This document maps AlphaPilot demo controls to selected SFC-aligned expectations from 2024-2026 guidance.
- This project is a technical demonstration and is **not** an SFC compliance certification.

## Control Mapping

| Control Objective | Implementation Evidence | Test Evidence | Status | Notes |
| --- | --- | --- | --- | --- |
| Request traceability for AI runs | `alphapilot/api/main.py`, `alphapilot/governance/audit.py`, `ai_audit_records` persistence | `test/test_audit_record.py`, `test/test_audit_wiring.py` | Implemented | Request ID propagated and persisted. |
| Evidence-backed outputs and citation checks | `alphapilot/services/citations.py`, `alphapilot/governance/claim_validation.py` | `test/test_claim_validation.py` | Implemented | Missing or invalid citations become blocking issues. |
| Human approval before publication | `alphapilot/governance/approvals.py`, approval APIs in `alphapilot/api/main.py` | `test/test_approval_state_machine.py`, `test/test_approval_api_permissions.py` | Implemented | Publish blocked unless approved. |
| Prompt security and sensitive-input rejection | `alphapilot/governance/prompt_security.py` | `test/test_prompt_security.py`, `test/test_sensitive_scanner.py` | Implemented | Prompt-injection/secrets/PII checks are enforced. |
| Kill switch and failure-safe degradation | `alphapilot/governance/kill_switch.py`, fallback handling in `alphapilot/api/main.py` | `test/test_kill_switch.py` | Implemented | Output/publication can be paused; provider errors return degraded response. |
| Audit export for governance review | `/analyses/{id}/audit/export` in `alphapilot/api/main.py` | `test/test_audit_export.py` | Implemented | Export is owner-scoped and allowlisted. |
| UI disclosure and review actions | `frontend/src/pages/AnalysisDetailPage.tsx` | Manual demo run | Implemented (Demo) | Governance card, review actions, and disclaimer shown in detail view. |

## Open Items / Limitations

- Formal regulatory interpretation and legal sign-off are out of scope for this demo.
- Named control owners and approver roster are not finalized in code/documentation yet.
- Model/prompt version capture is partially provisioned in schema and requires stricter operational policy.
