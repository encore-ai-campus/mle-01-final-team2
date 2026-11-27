# LLM condition extractor implementation and pilot status

Date: 2026-11-26 (Asia/Seoul)

## Status

The isolated `llm_only` path and synthetic validation are implemented. Live inference and the 10-notice pilot are BLOCKED because this workspace has no configured provider. The pasted work order also ends during section 12, immediately after saying that 10 of the 30 development notices should be used; pilot selection criteria and later sections were not present. No notices were sent to a model and no gold data was read by the extractor.

## Provider preflight

The project already defines an OpenAI-compatible self-hosted `vllm_primary` provider in `config/models.yaml`. It uses JSON-in-prompt validation rather than provider JSON Schema mode, a 60-second timeout, zero SDK retries, one format/schema retry, and an 800-token output limit. The adapter reuses `agent.llm.providers.OpenAICompatProvider` when configured.

Preflight found `VLLM_BASE_URL` and `VLLM_MODEL` unset, and the current virtual environment lacks `openai` and `pydantic`. No endpoint, model name, API key, or response content was logged. To enable a later live run, configure `VLLM_BASE_URL` and `VLLM_MODEL` in the local environment; `VLLM_API_KEY` and `VLLM_TIMEOUT_S` are optional. Install the project's existing LLM client dependencies. Then pin only DEVELOPMENT IDs in a JSON array and run:

```powershell
.\.venv\Scripts\python.exe tools/extract_condition_candidates_llm.py --execute --notice-ids-file <development_ids.json>
```

The preflight command is safe and prints only configuration booleans and missing variable names:

```powershell
.\.venv\Scripts\python.exe tools/extract_condition_candidates_llm.py --check-config
```

## Implementation

- `tools/extract_condition_candidates_llm.py` provides a separate `llm_only` path. It does not change the baseline or rule-based extractors.
- The model receives only the notice title, source system, excerpt, completeness status, field definition, extraction instructions, and an intermediate JSON Schema. Gold IDs, gold answers, alignments, and evaluation IDs are excluded from the request payload.
- The intermediate response is checked with JSON Schema. The Python mapper validates operators, values, units, phases, condition types, source fields, external-reference state, and exact quote presence before creating v1.1 artifacts.
- Character offsets are computed locally. Missing or repeated quotes, unsupported attributes, invalid values, or polarity conflicts are held for review; the model cannot supply offsets.
- Candidate and logic proposals remain `UNREVIEWED`; decision eligibility/readiness remain false. Empty model output is routed to review and never establishes that the notice has no conditions.
- Artifacts are isolated under `data/evaluations/conditions/v1.1/20261126/llm_pilot/`: `llm_condition_predictions.jsonl`, `condition_interpretations.jsonl`, `notice_condition_sets.jsonl`, `logic_proposals.jsonl`, `intermediate_responses.jsonl`, `review_queue.jsonl`, `schema_errors.jsonl`, and `run_report.json`.
- The pilot runner reads only the v1 condition extraction inputs and representative-sample split manifest, and rejects IDs outside DEVELOPMENT.

## Synthetic validation

`tests/test_condition_llm_extractor.py` covers the requested 20 safety/error cases, two end-to-end pilot checks, and two auxiliary logic/exception evidence checks. The 24 tests pass, including JSON/schema errors, condition and logic evidence, repeated-quote handling, value/type mismatch, condition polarity, post-selection phase, unresolved scope, duplicate handling, timeout/retry/provider failures, no-condition uncertainty, no auto-approval, gold/evaluation prompt exclusion, prompt injection, artifact schema validity, and evaluation-split rejection.

The final full repository suite completed with 217 tests: 189 passed and 28 skipped due to optional agent/API dependencies. `pytest` is not installed in the current environment; the project tests were run with `unittest`.

## Limits

- No real 10-notice pilot results, usage, latency, or extraction quality are available until provider configuration is supplied.
- The source order did not include the rest of section 12 or any later pilot sampling/evaluation requirements. This implementation therefore accepts externally pinned DEVELOPMENT IDs instead of inventing a sample or seed.
- The Python validator verifies schema and string/offset integrity, not full semantic truth. Every output stays in human review.
- Baseline, goldset, schema, extractor, logic-transformer, evaluation split, and database were not intentionally changed by this implementation. No commit or push was made.
