"""Offline contract tests for R2 generation and request accounting."""
import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import extract_condition_candidates_llm as llm
from tools import run_condition_llm_openai_pilot_r2 as r2


class FakeCompletions:
    def __init__(self, *, content='{}', finish='stop'):
        self.calls = []
        self.content, self.finish = content, finish

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(model=kwargs['model'], id='synthetic-response',
            choices=[SimpleNamespace(finish_reason=self.finish,
                message=SimpleNamespace(content=self.content, refusal=None))],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=20,
                completion_tokens_details=SimpleNamespace(reasoning_tokens=3)))


class FakeProvider:
    model = 'gpt-5.6-luna'
    name = 'synthetic'
    def __init__(self, text='', finish_reason=None):
        self.text = text
        self.last_response = {'finish_reason': finish_reason, 'response_text_length': len(text)}
        self.last_error = {}

    async def generate(self, messages, schema=None):
        return SimpleNamespace(text=self.text, usage={'prompt_tokens': 1, 'completion_tokens': 5,
                                                       'reasoning_tokens': 5}, metadata=self.last_response)


class R2ContractTests(unittest.IsolatedAsyncioTestCase):
    def retry_fixture(self, root, error='CONNECTION_ERROR'):
        out = Path(root)
        nid = 'SYN:0'
        old = {'model_id': 'gpt-5.6-luna', 'prompt_sha256_after': 'same',
               'runner_sha256': 'old-runner', 'extractor_sha256': 'old-extractor'}
        new = {**old, 'runner_sha256': 'new-runner', 'extractor_sha256': 'new-extractor'}
        r2.prior.write_json(out / 'manifest.json', {'fingerprint': old, 'status': 'LEAD_BLOCKED', 'requests_used': 2})
        r2.prior.write_json(out / 'request_ledger.json', {'limit': 12, 'used': 2,
            'attempts': [{'request_ordinal': 1, 'notice_id': 'SYNTHETIC:STRUCTURED_JSON_PREFLIGHT'},
                         {'request_ordinal': 2, 'notice_id': nid}]})
        r2.prior.write_json(out / 'synthetic_preflight.json', {'status': 'PASS'})
        r2.prior.write_json(out / 'lead_gate.json', {'status': 'BLOCKED'})
        r2.prior.write_json(out / 'lead/run_report.json', {'failure_count': 1})
        llm._write_jsonl(out / 'lead/per_notice_execution.jsonl',
            [{'notice_id': nid, 'status': error, 'error_code': 'APIConnectionError' if error == 'CONNECTION_ERROR' else 'INVALID_JSON'}])
        llm._write_jsonl(out / 'lead/llm_condition_predictions.jsonl', [])
        llm._write_jsonl(out / 'lead/raw_llm_responses.jsonl', [{'notice_id': nid, 'response_attempts': []}])
        return out, old, new, [nid, 'SYN:1']

    async def test_generation_settings_and_metadata(self):
        provider = llm.OpenAIDirectProvider(api_key='synthetic-only', model='gpt-5.6-luna',
                                            timeout_s=180, max_completion_tokens=8192,
                                            reasoning_effort='low')
        fake = FakeCompletions(content='{"ok":true}')
        provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
        result = await provider.generate([{'role': 'user', 'content': 'synthetic'}])
        self.assertEqual(fake.calls[0]['max_completion_tokens'], 8192)
        self.assertEqual(fake.calls[0]['reasoning_effort'], 'low')
        self.assertEqual(fake.calls[0]['response_format'], {'type': 'json_object'})
        self.assertEqual(result.metadata['finish_reason'], 'stop')
        self.assertEqual(result.metadata['response_text_length'], 11)
        self.assertEqual(provider.client.chat.completions.calls[0]['model'], 'gpt-5.6-luna')

    async def test_length_empty_and_invalid_json_are_distinct(self):
        row = {'notice_id': 'SYN:1', 'source_system': 'SYN', 'raw_text': 'synthetic'}
        for finish, text, expected in [('length', '', 'OUTPUT_TOKEN_LIMIT'),
                                       (None, '', 'EMPTY_RESPONSE'),
                                       ('stop', '{oops', 'INVALID_JSON')]:
            with self.subTest(expected=expected):
                with self.assertRaises(llm.ExtractionFailure) as caught:
                    await llm.call_and_parse(FakeProvider(text, finish), row, max_format_attempts=1)
                self.assertEqual(caught.exception.status, expected)

    async def test_ledger_persists_and_enforces_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.json'
            budget = r2.LedgerBudget(path)
            budget.label = 'SYN:1'
            self.assertTrue(budget.consume())
            self.assertEqual(r2.LedgerBudget(path).used, 1)
            saved = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(saved['attempts'][0]['request_ordinal'], 1)
            budget.used = budget.limit
            self.assertFalse(budget.consume())

    async def test_existing_output_is_refused_without_provider_call(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'old-result').write_text('preserve', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_ALREADY_EXISTS'):
                r2.lead(out, Path('.env'), ['SYN:1'], {})
            self.assertEqual((out / 'old-result').read_text(encoding='utf-8'), 'preserve')

    async def test_vllm_configuration_still_uses_existing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / '.env'
            env.write_text('CONDITION_LLM_PROVIDER=vllm_primary\nVLLM_BASE_URL=http://localhost:8000/v1\nVLLM_MODEL=synthetic\n', encoding='utf-8')
            status = llm.llm_connection_status(env)
            self.assertEqual(status['provider'], 'vllm_primary')
            self.assertEqual(status['required_environment_variables'], ['VLLM_BASE_URL', 'VLLM_MODEL'])

    async def test_failed_lead_blocks_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            r2.prior.write_json(out / 'manifest.json', {'fingerprint': {}, 'status': 'LEAD_BLOCKED'})
            with self.assertRaisesRegex(RuntimeError, 'LEAD_GATE_NOT_PASSED'):
                r2.resume(out, Path('.env'), ['SYN:1', 'SYN:2'], {})
            self.assertFalse((out / 'notice_01').exists())

    async def test_successful_notice_directories_are_reused_without_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            ids = ['SYN:0'] + [f'SYN:{n}' for n in range(1, 10)]
            r2.prior.write_json(out / 'manifest.json', {'fingerprint': {}, 'status': 'REMAINING_IN_PROGRESS'})
            r2.prior.write_json(out / 'lead_gate.json', {'status': 'PASS'})
            for index, nid in enumerate(ids[1:], 1):
                path = out / f'notice_{index:02d}'
                r2.prior.write_json(path / 'run_report.json', {'failure_count': 0})
                llm._write_jsonl(path / 'per_notice_execution.jsonl', [{'notice_id': nid, 'status': 'COMPLETED'}])
            with patch.object(r2, 'provider_from_env', return_value=object()), \
                 patch.object(r2.llm, 'run_pilot', side_effect=AssertionError('duplicate call')):
                self.assertEqual(r2.resume(out, Path('.env'), ids, {}), 0)
            self.assertEqual(r2.prior.read_json(out / 'manifest.json')['status'], 'ALL_TEN_EXTRACTED')

    async def test_reserved_request_without_result_cannot_be_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            ids = ['SYN:0', 'SYN:1']
            r2.prior.write_json(out / 'manifest.json', {'fingerprint': {}, 'status': 'LEAD_PASSED'})
            r2.prior.write_json(out / 'lead_gate.json', {'status': 'PASS'})
            r2.prior.write_json(out / 'request_ledger.json', {'limit': 12, 'used': 1,
                'attempts': [{'request_ordinal': 1, 'notice_id': 'SYN:1', 'state': 'RESERVED_BEFORE_API_CALL'}]})
            with patch.object(r2, 'provider_from_env', return_value=object()), \
                 patch.object(r2.llm, 'run_pilot', side_effect=AssertionError('duplicate call')):
                with self.assertRaisesRegex(RuntimeError, 'REQUEST_RESERVED_WITHOUT_RESULT'):
                    r2.resume(out, Path('.env'), ids, {})

    async def test_connection_error_retry_preparation_preserves_fingerprint_and_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            out, old, new, ids = self.retry_fixture(directory)
            before = r2.prior.digest(out / 'request_ledger.json')
            lead_before = r2.prior.digest(out / 'lead/per_notice_execution.jsonl')
            self.assertEqual(r2.prepare_retry(out, ids, new), 0)
            self.assertEqual(r2.prior.read_json(out / 'manifest.json')['fingerprint'], old)
            self.assertEqual(r2.prior.digest(out / 'request_ledger.json'), before)
            self.assertEqual(r2.prior.digest(out / 'lead/per_notice_execution.jsonl'), lead_before)
            self.assertEqual(r2.assert_same_run(out / 'manifest.json', new)['status'], 'LEAD_BLOCKED')
            with self.assertRaisesRegex(RuntimeError, 'RETRY_PREPARATION_NOT_ALLOWED'):
                r2.prepare_retry(out, ids, new)

    async def test_non_connection_error_and_setting_change_block_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            out, _, new, ids = self.retry_fixture(directory, error='INVALID_JSON')
            with self.assertRaisesRegex(RuntimeError, 'PRIOR_LEAD_IS_NOT_RETRYABLE'):
                r2.prepare_retry(out, ids, new)
            changed = {**new, 'model_id': 'other-model'}
            with self.assertRaisesRegex(RuntimeError, 'R2_INPUT_OR_SETTINGS_CHANGED'):
                r2.prepare_retry(out, ids, changed)

    async def test_prior_response_blocks_connection_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            out, _, new, ids = self.retry_fixture(directory)
            llm._write_jsonl(out / 'lead/raw_llm_responses.jsonl',
                [{'notice_id': ids[0], 'response_attempts': ['{"status":"CONDITIONS_FOUND"}']}])
            with self.assertRaisesRegex(RuntimeError, 'PRIOR_LEAD_IS_NOT_RETRYABLE'):
                r2.prepare_retry(out, ids, new)

    async def test_retry_success_uses_one_request_and_keeps_first_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            out, old, new, ids = self.retry_fixture(directory)
            r2.prepare_retry(out, ids, new)
            original_hash = r2.prior.digest(out / 'lead/raw_llm_responses.jsonl')
            async def fake_run(provider, notice_ids, *, output_dir, request_budget, max_format_attempts):
                request_budget.consume()
                r2.prior.write_json(output_dir / 'run_report.json', {'failure_count': 0, 'schema_error_count': 0})
                llm._write_jsonl(output_dir / 'per_notice_execution.jsonl',
                    [{'notice_id': ids[0], 'status': 'COMPLETED', 'provider_metadata': {'finish_reason': 'stop'}}])
                llm._write_jsonl(output_dir / 'raw_llm_responses.jsonl',
                    [{'notice_id': ids[0], 'response_attempts': ['{"status":"CONDITIONS_FOUND"}']}])
                llm._write_jsonl(output_dir / 'rejected_candidates.jsonl', [])
                return {'failure_count': 0, 'condition_count': 1, 'schema_error_count': 0,
                        'held_review_queue': 0, 'decision_eligible_true_count': 0, 'status_counts': {'COMPLETED': 1}}
            with patch.object(r2, 'provider_from_env', return_value=object()), \
                 patch.object(r2.llm, 'run_pilot', side_effect=fake_run):
                self.assertEqual(await asyncio.to_thread(r2.retry_lead, out, Path('.env'), ids, new), 0)
            self.assertEqual(r2.prior.read_json(out / 'request_ledger.json')['used'], 3)
            self.assertEqual(r2.prior.read_json(out / 'manifest.json')['status'], 'LEAD_PASSED')
            self.assertEqual(r2.prior.read_json(out / 'lead_retry_gate.json')['status'], 'PASS')
            self.assertEqual(r2.prior.digest(out / 'lead/raw_llm_responses.jsonl'), original_hash)
            with self.assertRaisesRegex(RuntimeError, 'LEAD_RETRY_NOT_ALLOWED'):
                r2.retry_lead(out, Path('.env'), ids, new)

    async def test_retry_failure_keeps_followup_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            out, _, new, ids = self.retry_fixture(directory)
            r2.prepare_retry(out, ids, new)
            async def failed_run(provider, notice_ids, *, output_dir, request_budget, max_format_attempts):
                request_budget.consume()
                r2.prior.write_json(output_dir / 'run_report.json', {'failure_count': 1})
                llm._write_jsonl(output_dir / 'per_notice_execution.jsonl',
                    [{'notice_id': ids[0], 'status': 'CONNECTION_ERROR'}])
                llm._write_jsonl(output_dir / 'raw_llm_responses.jsonl',
                    [{'notice_id': ids[0], 'response_attempts': []}])
                llm._write_jsonl(output_dir / 'rejected_candidates.jsonl', [])
                return {'failure_count': 1, 'condition_count': 0, 'schema_error_count': 0,
                        'held_review_queue': 1, 'decision_eligible_true_count': 0,
                        'status_counts': {'CONNECTION_ERROR': 1}}
            with patch.object(r2, 'provider_from_env', return_value=object()), \
                 patch.object(r2.llm, 'run_pilot', side_effect=failed_run):
                self.assertEqual(await asyncio.to_thread(r2.retry_lead, out, Path('.env'), ids, new), 2)
            self.assertEqual(r2.prior.read_json(out / 'manifest.json')['status'], 'LEAD_BLOCKED')
            with self.assertRaisesRegex(RuntimeError, 'LEAD_GATE_NOT_PASSED'):
                r2.resume(out, Path('.env'), ids, new)


if __name__ == '__main__':
    unittest.main()
