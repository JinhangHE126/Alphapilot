# Model Card (Demo)

## Model Usage Context

- Primary purpose: Generate draft equity research content and structured analysis outputs.
- Deployment mode: API-based model calls via configured providers with multi-agent orchestration.
- Human-in-the-loop: Required before publication.

## Inputs and Outputs

- Inputs: User prompt, stock symbol, retrieved evidence chunks, system instructions.
- Outputs: Draft analysis report, recommendation text, intermediate agent outputs, guard assessment.

## Safety and Governance Controls

- Prompt security scanning for injection patterns and sensitive data.
- Evidence-backed citation extraction and claim validation.
- Guard hard-rule checks with blocking issues.
- Kill switch for output/publication pause.
- Approval workflow and owner-scoped governance actions.

## Known Limitations

- Output quality can degrade under sparse or low-quality evidence.
- External provider availability and latency affect runtime behavior.
- Models may still produce persuasive but weakly supported prose that requires reviewer scrutiny.

## Failure Handling

- Provider/model exception path returns degraded response and records `ANALYSIS_FAILED`.
- Failed/blocked flows are persisted in audit trail with risk flags.

## Non-Claims

- This model card does not claim formal regulatory approval or production-grade model risk sign-off.
