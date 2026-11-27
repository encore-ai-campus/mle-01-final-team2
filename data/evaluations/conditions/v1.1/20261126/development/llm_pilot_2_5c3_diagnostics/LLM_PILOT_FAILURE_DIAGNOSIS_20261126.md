# OpenAI LLM pilot failure diagnosis — 2026-11-26

## Scope and preservation

Read-only diagnosis of `development/llm_pilot_2_5c3_localrun/`. No API requests were made. The failed run outputs, request tally, goldset, evaluation policy, and baselines were not modified. Per-notice evidence is summarized in `per_notice_failure_diagnosis.csv`.

## Findings

- The synthetic structured-JSON preflight succeeded with `gpt-5.6-luna`: one request returned a locally schema-valid JSON object. It used 1,673 input, 275 completion, and 81 reasoning tokens. This shows that the configured model and Chat Completions JSON mode can return parseable output.
- The ten notice calls yielded one `PROVIDER_ERROR` and nine `INVALID_RESPONSE`; no condition artifact was produced. The run status is `PILOT_INCOMPLETE_NO_SCORING` and the manifest records 12/12 conservatively counted requests.
- In all nine `INVALID_RESPONSE` rows, the saved text passed to the JSON parser is empty (`response_attempts: [""]`). Each used exactly 800 completion tokens, all 800 reported as reasoning tokens. The 800-token completion ceiling was therefore exhausted before visible JSON was saved. This is the strongly supported root cause; exact API `finish_reason` was not persisted, so `finish_reason=length` cannot be independently confirmed from this run.
- The local parser labels an empty string `INVALID_JSON_OR_TRUNCATED_OUTPUT`; it does not distinguish token truncation from other empty-content cases. This explains the recorded status but is not evidence of a malformed non-empty JSON body.
- The one `PROVIDER_ERROR` is recorded only as `APIConnectionError`, with zero usage, 0 ms, and no raw response. No HTTP status, provider error code, request ID, or exception message was saved. Its precise network cause cannot be recovered from these artifacts. It is separate from the nine output-limit failures.
- The recorded 16,360 prompt / 7,200 completion / 7,200 reasoning tokens cover notice calls. The separate successful synthetic preflight adds 1,673 / 275 / 81 respectively, for a recorded total of 18,033 input, 7,475 completion, and 7,281 reasoning tokens across successful calls. The provider-error call had no usage record.

## Response-mode and model-parameter compatibility

The runner sends `response_format={"type":"json_object"}` and locally validates against the intermediate JSON Schema. OpenAI documents JSON mode for compatible GPT-5 models; the successful synthetic response is direct evidence that this mode worked for the configured model in this run. JSON mode guarantees JSON syntax in ordinary completed responses, but does not enforce the supplied schema; local validation remains necessary. This makes response-mode incompatibility an unlikely cause of these nine failures.

The runner sends `max_completion_tokens=800` and does not send `reasoning_effort`. OpenAI defines `max_completion_tokens` to include visible output and reasoning tokens. The GPT-5.6 Luna model page lists reasoning-effort values `none`, `low`, `medium`, `high`, `xhigh`, and `max`; absent an explicit setting, the documented default is `medium`. Thus 800 reasoning tokens consumed the entire current output budget. Sources: [GPT-5.6 Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Chat Completions create reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning?api-mode=chat).

## Minimal changes proposed for a separately authorized experiment

1. Raise `max_completion_tokens` from 800 to 8,192 for the next bounded pilot. The documented model output limit allows this value. If cost/latency constraints favor a smaller first retry, 4,096 is a lower-risk starting cap, with a chance of repeating the truncation on the most complex notices.
2. Set `reasoning_effort="low"` explicitly for this extraction task. This is a supported GPT-5.6 Luna value and should reduce reasoning-token use; it does not guarantee a particular token count or extraction quality. Do not use `none` in the initial retest unless a separate quality check supports it.
3. Preserve response metadata before converting it to text: `finish_reason`, refusal state, returned model, response ID, and usage detail. Classify `finish_reason=length` or an explicit incomplete status as `OUTPUT_TRUNCATED`; classify non-empty unparsable text separately as `INVALID_JSON`; keep empty content with no truncation marker as `EMPTY_MODEL_CONTENT`.
4. For provider exceptions, retain only sanitized exception type, HTTP status, provider error code, and request ID when available. The current error message cannot be reconstructed; never log credentials, request headers, or source payloads as error context.
5. Keep JSON mode and local schema validation for the first retest. Switching to strict `json_schema` should wait until a provider-compatible schema projection is prepared: the current intermediate schema uses composition such as `oneOf`, which the strict Structured Outputs subset may reject.

## New request budget proposal

The completed experiment remains recorded as 12/12; do not reset or reuse it. A separate run ID and separately authorized cap of 12 requests is proposed for the retest:

- 1 synthetic JSON preflight;
- 10 frozen development notices, one attempt each;
- 1 contingency request for a single transient/API-format failure.

Keep SDK automatic retries disabled. Use the contingency at most once and record which notice used it. If a notice is still incomplete or invalid after the allowed attempt, stop scoring and preserve an incomplete status. Do not include independent evaluation notices.

## Per-notice classification

See `per_notice_failure_diagnosis.csv`. `finish_reason` and the original response envelope are `NOT_RECORDED` for all rows because the current adapter stores only message text and token usage. In particular, the one provider error's exact message/status cannot be supplied from available files.

## Artifact state

- Existing failure manifest: `PILOT_INCOMPLETE_NO_SCORING`, with 12 conservatively counted attempts.
- Existing 9 notice error codes: `INVALID_JSON_OR_TRUNCATED_OUTPUT`; 1: `APIConnectionError`.
- Existing predictions: zero before validation and zero after validation.
- No evaluation scores were created.
- All referenced input, goldset, and baseline hashes were only read; none were changed by this diagnosis.
