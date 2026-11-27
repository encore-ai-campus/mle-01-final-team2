# LLM pilot execution blocker — 2026-11-26

## Status

The frozen 10-notice pilot is **not executed**. No LLM prediction, condition score, or model-generated source text was produced.

## Completed locally

- The pilot IDs, source split, finalized v1.1 gold hashes, v1 input hash, v1 baseline hashes, rule experiment E hashes, and evaluator hash matched the frozen preparation manifest.
- OpenAI direct configuration is present (`OPENAI_API_KEY` and `OPENAI_CHAT_MODEL`); secret values were not printed or written.
- The dedicated OpenAI adapter, JSON mode, local v1.1 validation, pre/post-validation artifacts, and strict same-sample comparison runner were implemented.
- 29 LLM extractor synthetic tests passed. The full suite passed: 222 tests, 28 skipped.

## Blocker

The first ordinary sandbox attempt could not connect to the OpenAI API (`APIConnectionError`). The user then explicitly approved transmitting the fixed 10 development notice excerpts. The escalated run was unable to read the local source input (`PermissionError` on `data/condition_inputs/v1/20261125/extraction_inputs.jsonl`) and stopped before making an API request. The automatic approval reviewer had previously rejected the external transmission because the user’s explicit consent had not yet been obtained; that consent is now present.

The execution environment therefore cannot both read the protected workspace input and reach the external API in one approved run. No fallback or indirect transmission was attempted.

## Request cap and next action

The configured cap is 12 requests. One unsuccessful connection attempt is conservatively reserved in that count. If execution is enabled in an environment that can read the workspace and reach the official API, run `tools/run_condition_llm_openai_pilot.py`; the script uses one synthetic JSON preflight plus at most 10 notice calls and counts the prior attempt, keeping the total at or below 12.

The API preflight, raw responses, predictions, metrics, and cost estimate remain absent until that run succeeds.
