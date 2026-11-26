# 2-5C-3C-R2 staged local pilot readiness

The old failed run stays at `data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_localrun/` with 12/12 requests consumed. R2 uses a separate run ID and output path: `data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_r2/`. Preparation and tests make no API calls. Do not execute `--lead` until the user explicitly authorizes a new request budget.

R2 pins `gpt-5.6-luna`, `reasoning_effort=low`, `max_completion_tokens=8192`, `timeout=180` seconds, JSON object mode, SDK retries 0, the unchanged prompt, and the existing local v1.1 schema check. The official [model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna) lists `low` reasoning effort and a 128,000-token output ceiling; the [Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) supports both request parameters.

Run from the project root in Windows PowerShell using the existing `.venv` and `.env`:

```powershell
Set-Location 'C:\Users\rhksa\Desktop\mle-01-final-team2'
& '.\.venv\Scripts\python.exe' tools/run_condition_llm_openai_pilot_r2.py --check
```

`--check` is offline. It verifies readable inputs, development-only frozen IDs, gold and baseline hashes, previous failure reference, model ID, prompt hash, and code fingerprint. All `readable_inputs` entries and frozen checks must be true. It does not print the API key.

**After explicit authorization of a new, separate 12-request budget**, execute the technical gate:

```powershell
& '.\.venv\Scripts\python.exe' tools/run_condition_llm_openai_pilot_r2.py --lead --authorize-new-budget
```

This consumes at most two new requests: one synthetic JSON preflight and one call for `BIZINFO:PBLN_000000000117168`. Inspect `llm_pilot_2_5c3_r2/lead_gate.json`, `lead/per_notice_execution.jsonl`, and `request_ledger.json`. Proceed only when the gate status is `PASS`. A failed gate stops without calling the other nine notices.

Then continue the remaining nine once:

```powershell
& '.\.venv\Scripts\python.exe' tools/run_condition_llm_openai_pilot_r2.py --continue
```

The runner checks the manifest fingerprint and the durable request ledger before each notice, reuses completed notice directories, and stops on a failed call. It records any unprocessed IDs in `remaining_failure.json`. A request reserved before a process interruption cannot be silently repeated. The twelfth request remains a contingency; this runner does not automatically use it.

After `manifest.json` says `ALL_TEN_EXTRACTED`, evaluate the frozen ten notices and 62 gold conditions:

```powershell
& '.\.venv\Scripts\python.exe' tools/run_condition_llm_openai_pilot_r2.py --evaluate
```

The evaluation uses the existing v1.1 strict matcher and writes `evaluation_summary.json` and `pilot_baseline_comparison.csv`. It scores conditions only after all ten calls passed technical validation. Gold data is read after extraction. No logic semantic score is produced.

Each stage preserves raw model text, before/after-validation candidates, held/rejected records, token counts, request ordinals, finish reasons, refusal state, response lengths, HTTP status and request ID where available, and sanitized provider errors. The SDK may not provide an HTTP response for a connection failure; those fields remain null. All candidates remain unreviewed and decision-ineligible.
