# Evaluation Report (Demo)

## Evaluation Scope

- Validate day-1 governance controls for auditability, approval gating, prompt safety, kill switch, and export.
- Confirm owner-based API access control for governance endpoints.

## Automated Test Commands

```bash
python -m pytest \
  alphapilot/test/test_approval_api_permissions.py \
  alphapilot/test/test_audit_export.py \
  alphapilot/test/test_kill_switch.py \
  alphapilot/test/test_prompt_security.py \
  alphapilot/test/test_approval_state_machine.py \
  alphapilot/test/test_claim_validation.py \
  alphapilot/test/test_audit_wiring.py \
  alphapilot/test/test_audit_record.py -q
```

## Automated Test Result

- Result: `37 passed`
- Outcome: PASS for governance regression subset.
- Warnings observed: framework/model deprecation warnings and `datetime.utcnow()` deprecation in repository helper (non-blocking for demo scope).

## Manual Verification Summary

- Governance card is visible in analysis detail page (`/history/{id}`).
- Approval actions rendered according to status (submit/approve/reject/revision/publish).
- Audit export button available and owner-scoped.
- Disclaimer text visible in UI.

## Coverage Against Acceptance Criteria

| Acceptance Need | Evidence |
| --- | --- |
| Guard-failed reports cannot enter approval flow | `test/test_approval_state_machine.py` |
| Unapproved reports cannot publish | `test/test_approval_state_machine.py` |
| Prompt injection / sensitive-input handling | `test/test_prompt_security.py` |
| Kill switch pauses output/publication | `test/test_kill_switch.py` |
| Audit export includes governance payload | `test/test_audit_export.py` |
| Non-owner blocked from governance endpoints | `test/test_approval_api_permissions.py` |

## Remaining Limitations

- Frontend build/test toolchain has pre-existing unrelated issues outside governance acceptance scope.
- Formal compliance/legal sign-off is not part of this demo and remains pending.
