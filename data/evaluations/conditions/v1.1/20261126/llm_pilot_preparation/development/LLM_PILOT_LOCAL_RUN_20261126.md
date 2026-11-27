# LLM pilot: local PowerShell run guide (2026-11-26)

Run this only from the Windows workstation where the project `.venv` and `.env` are available. The guide does not change `.env`, install packages, or print the API key.

## Request budget

The earlier sandbox connection attempt is reserved as one of the 12 permitted attempts. Its delivery was not confirmed, so it is counted conservatively. The local runner has an 11-attempt budget: one synthetic JSON preflight plus one attempt for each of the ten frozen development notices. SDK retries and per-notice format retries are disabled. The runner records both the attempts made during the local run and the conservative total including the earlier connection attempt. Do not reset the budget or rerun after a partial run without reviewing the request record.

## 1. Open the project in PowerShell

```powershell
Set-Location 'C:\Users\rhksa\Desktop\mle-01-final-team2'
```

## 2. Confirm the local environment without exposing the key

```powershell
$keyLine = Select-String -Path '.env' -Pattern '^\s*OPENAI_API_KEY\s*=' | Select-Object -First 1
$keyConfigured = $false
if ($keyLine) {
    $keyValue = (($keyLine.Line -split '=', 2)[1].Trim().Trim('"').Trim("'"))
    $keyConfigured = -not [string]::IsNullOrWhiteSpace($keyValue)
    Remove-Variable keyValue
}
if ($keyConfigured) { 'OPENAI_API_KEY=SET' } else { 'OPENAI_API_KEY=MISSING' }
$modelLine = Select-String -Path '.env' -Pattern '^\s*OPENAI_CHAT_MODEL\s*=' | Select-Object -First 1
if ($modelLine) { 'OPENAI_CHAT_MODEL=' + (($modelLine.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")) } else { 'OPENAI_CHAT_MODEL=MISSING' }
```

Expected: the key check prints only `SET` or `MISSING`; the model check prints the configured model identifier. Never paste or share the key value.

## 3. Check dependencies and provider configuration

The existing virtual environment can be used directly; activation is optional.

```powershell
& '.\.venv\Scripts\python.exe' 'tools/extract_condition_candidates_llm.py' --provider openai_direct --check-config
```

Proceed only when the JSON output has `"configured": true`, both required variables are present, and `openai`/`pydantic` dependencies show `true`. This command is local-only and does not contact the API. Do not run `pip install` for this pilot.

## 4. Verify frozen sample and baseline hashes (offline)

```powershell
& '.\.venv\Scripts\python.exe' -c "import json; from tools.run_condition_llm_openai_pilot import PREPARATION, read_json, verify_frozen_inputs; print(json.dumps(verify_frozen_inputs(read_json(PREPARATION / 'pilot_notice_ids.json')), ensure_ascii=False, indent=2))"
```

Expected: every entry under `checks` is `true`. This verifies the fixed 10 IDs (5 per source), development-only split, finalized goldset hashes, input v1, baseline v1, rule experiment E, and evaluator. It makes no API request and prints no API credentials. Stop if an error is raised or any check is false.

## 5. Run the fixed 10-notice extraction and evaluation

This is the only run command required. It performs the synthetic JSON preflight, calls the configured model for the frozen 10 notices, validates candidates, and then evaluates the pre-validation and post-validation condition predictions against the same 10 gold notices. Logic semantics are not scored.

```powershell
& '.\.venv\Scripts\python.exe' 'tools/run_condition_llm_openai_pilot.py'
```

The command uses the official OpenAI SDK endpoint, the existing `OPENAI_CHAT_MODEL`, and `.env` key. No model, endpoint, or sample override is passed. The output directory must be new or empty; the default is `data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_localrun/` so the earlier blocker record remains untouched.

On success, expect exit code 0 and status `PILOT_COMPLETED` in `evaluation_summary.json`. On API or synthetic preflight failure, inspect `preflight_blocker.json`. If an individual notice call fails, partial outputs are kept, status is `PILOT_INCOMPLETE_NO_SCORING`, and no performance scores are generated. Do not rerun automatically; first reconcile the request tally.

## Outputs to inspect

In the default local-run directory:

- Raw model output: `raw_llm_responses.jsonl`
- Proposed conditions before validation: `predictions_before_validation.jsonl`
- Candidates after validation: `predictions_after_validation.jsonl` and `llm_condition_predictions.jsonl`
- Rejected/held candidates and reasons: `rejected_candidates.jsonl`, `validation_details.jsonl`, `review_queue.jsonl`
- API attempts, status, duration, and token usage: `per_notice_execution.jsonl`, `run_report.json`, `api_preflight.json`
- Evaluation summary and same-sample comparison: `evaluation_summary.json`, `pilot_baseline_comparison.csv`, `condition_match_details.csv`, `failure_analysis.csv`
- Request/input/output hashes: `manifest.json`

All generated candidates remain unreviewed and decision-ineligible. The 10-notice sample is diagnostic, not representative. The runner performs both extraction and evaluation, so no separate evaluation command is needed.
