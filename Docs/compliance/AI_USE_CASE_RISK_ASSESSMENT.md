# AI Use Case Risk Assessment (Demo)

## Use Case

- Name: AI-assisted equity research and recommendation drafting.
- System: AlphaPilot multi-agent workflow with evidence retrieval and guard checks.
- Intended users: Internal/demo users performing research support tasks.
- Out of scope: Fully automated execution trading and unsupervised publication.

## Risk Register

| Risk | Description | Inherent Risk | Mitigation | Residual Risk |
| --- | --- | --- | --- | --- |
| Hallucinated claims | Model output may include unsupported facts | High | Guard checks, citation validation, claim validation, human approval | Medium |
| Unsupported numeric statements | Report includes numbers without evidence | High | `UNSUPPORTED_NUMERIC_CLAIM` and citation blockers | Medium |
| Prompt injection / secret leakage | Malicious prompts or sensitive data leaks | High | Prompt security scan, sensitive scanner, rejection flow | Medium |
| Unauthorized workflow actions | Non-owner user attempts approve/publish/export | Medium | JWT auth + ownership checks in API routes | Low |
| Provider outage or model errors | Upstream API errors produce unstable outputs | Medium | Degraded fallback response + audit risk flags | Low |
| Uncontrolled publication | Report published without review | High | Approval state machine + publication gate + kill switch | Low |

## Mandatory Human Controls

- Reviewer identity is captured on approve/reject/revision actions.
- Publish is only allowed for approved records.
- Reject/revision actions require review comments.

## Remaining Gaps (Demo Limitations)

- Formal reviewer role segregation and enterprise IAM integration are not implemented.
- Data retention policy and incident SLAs require business/legal confirmation.
- Final production risk acceptance must be signed by designated business owner.
