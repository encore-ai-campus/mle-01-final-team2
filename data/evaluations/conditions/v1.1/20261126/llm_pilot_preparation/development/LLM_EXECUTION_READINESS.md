# LLM pilot execution readiness — 2026-11-26

## Frozen diagnostic sample

This 10-notice sample is for development failure diagnosis, not population-representative performance claims. It is selected from finalized goldset `conditions-development-v1.1-20261126-final30`; the extractor receives only notice IDs and v1 source inputs, never gold data.

Seed: `20261126`. Selection: two mandatory failure anchors plus source-stratified diagnostic coverage. The constrained slots had no unresolved ties; the seed and SHA-256 tie policy are recorded in `pilot_manifest.json`.

- `BIZINFO:PBLN_000000000117168` — Region plus applicant address, sustained-date condition, and AND scope.
- `BIZINFO:PBLN_000000000118182` — Required high-impact failure case: organization branches, exception, AND/OR.
- `BIZINFO:PBLN_000000000119490` — Employee threshold and regional hiring branches with AND/OR structure.
- `BIZINFO:PBLN_000000000126490` — No existing rule candidates; same-right IP attributes and unresolved binding.
- `BIZINFO:PBLN_000000000128028` — No existing rule candidates; applicant branches and basic/optional duties.
- `KSTARTUP:176001` — Simple numeric, business-age, and revenue-share thresholds.
- `KSTARTUP:176813` — Applicant/business OR branch, preference conditions, and an exception.
- `KSTARTUP:177447` — Team age condition with military-service age-band exception and evidence duties.
- `KSTARTUP:178507` — Required high-impact failure case: applicant branches, exclusions, temporal duty and exception.
- `KSTARTUP:179386` — Preference condition, open industry scope, and unresolved requirement relation.

Source allocation: BIZINFO 5, K-Startup 5. Evaluation overlap: 0. Rule E zero-prediction notices: 3.

## Same-sample existing results

These are computed using `evaluate_condition_pipeline_v11.evaluate_records`, the existing v1.1 evaluator implementation and strict exact matching, with only the ten frozen IDs. They are not comparable as full-development 30-notice scores.

| Model | Scope | TP | FP | FN | Precision | Recall | F1 | Macro F1 | Zero-prediction notices |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_v1 | OVERALL | 6 | 20 | 56 | 0.2308 | 0.0968 | 0.1364 | 0.1271 | 2 |
| baseline_v1 | SOURCE:BIZINFO | 1 | 6 | 34 | 0.1429 | 0.0286 | 0.0476 | — | 2 |
| baseline_v1 | SOURCE:KSTARTUP | 5 | 14 | 22 | 0.2632 | 0.1852 | 0.2174 | — | 0 |
| baseline_v1 | TYPE:ELIGIBILITY | 6 | 14 | 50 | 0.3000 | 0.1071 | 0.1579 | — | 0 |
| baseline_v1 | TYPE:EXCLUSION | 0 | 4 | 3 | 0.0000 | 0.0000 | 0.0000 | — | 0 |
| baseline_v1 | TYPE:PREFERENCE | 0 | 2 | 3 | 0.0000 | 0.0000 | 0.0000 | — | 0 |
| rule_experiment_E | OVERALL | 6 | 17 | 56 | 0.2609 | 0.0968 | 0.1412 | 0.1253 | 3 |
| rule_experiment_E | SOURCE:BIZINFO | 1 | 2 | 34 | 0.3333 | 0.0286 | 0.0526 | — | 3 |
| rule_experiment_E | SOURCE:KSTARTUP | 5 | 15 | 22 | 0.2500 | 0.1852 | 0.2128 | — | 0 |
| rule_experiment_E | TYPE:ELIGIBILITY | 6 | 11 | 50 | 0.3529 | 0.1071 | 0.1644 | — | 0 |
| rule_experiment_E | TYPE:EXCLUSION | 0 | 4 | 3 | 0.0000 | 0.0000 | 0.0000 | — | 0 |
| rule_experiment_E | TYPE:PREFERENCE | 0 | 2 | 3 | 0.0000 | 0.0000 | 0.0000 | — | 0 |

## Provider and dependencies

The existing dependency files declare and pin `openai` and `pydantic` (`requirements.txt`, `requirements.lock.txt`). Current `.venv` versions: `openai 2.54.0`, `pydantic 2.14.4`. Use the repository's pinned environment setup to recreate the environment; the pilot does not install packages or call an API automatically.

Install the locked project environment when package-index access is available:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
```

The app's generic `OPENAI_*` settings are not read by this pilot. Provider configurations are separated: existing `vllm_primary`/`vllm_alt` use `VLLM_*`; the optional `openai_direct` path requires dedicated `CONDITION_LLM_OPENAI_*` variables, an explicit provider selection, and an explicit base URL and model ID. The latter is an external-data path. Neither provider is selected here. “OpenAI LUNA 5.6” remains an unverified working label; no API model ID, endpoint, or credential is inferred.

Copy the commented examples from `condition_llm_pilot.env.example` into an untracked local environment file only after confirming the provider. Set `CONDITION_LLM_PROVIDER` explicitly to `vllm_primary`, `vllm_alt`, or `openai_direct`; an unset provider is blocked. Never commit secrets.

## Run after provider confirmation

The following command will be enabled only after the provider-specific endpoint, model ID, credentials, and local client dependencies are configured. It is capped at ten notices and twelve API requests, with at most one format-validation retry per notice:

```powershell
.\.venv\Scripts\python.exe tools/extract_condition_candidates_llm.py --execute --notice-ids-file data/evaluations/conditions/v1.1/20261126/llm_pilot_preparation/development/pilot_notice_ids.json --pilot-manifest data/evaluations/conditions/v1.1/20261126/llm_pilot_preparation/development/pilot_manifest.json --output-dir data/evaluations/conditions/v1.1/20261126/llm_pilot/development
```

Preflight without a call:

```powershell
.\.venv\Scripts\python.exe tools/extract_condition_candidates_llm.py --check-config
```

The execution report will preserve the raw response attempts, validated intermediate response, v1.1 candidates, held/invalid reasons, per-notice elapsed time, retry/failure counts, token usage, prompt version/hash, and output hashes. All outputs remain unreviewed and decision-ineligible. No LLM output or LLM score has been produced in this preparation step.

## Updated local OpenAI direct run instructions (2026-11-26)

The provider setup and legacy execution example above are superseded for the approved local OpenAI pilot. The current runner reads the existing `OPENAI_API_KEY` and `OPENAI_CHAT_MODEL`, uses the official OpenAI endpoint, performs strict evaluation after extraction, and counts the prior blocked connection attempt conservatively. Follow `LLM_PILOT_LOCAL_RUN_20261126.md` for the exact offline checks and the single execution command. Do not use the legacy dedicated `CONDITION_LLM_OPENAI_*` setup or the old extractor CLI example for this run.
