from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from tools import extract_condition_candidates_llm as llm
from tools import run_condition_llm_openai_pilot_r2_norm_v2 as runner


class OpenAIClientLifecycleTests(unittest.TestCase):
    def test_three_real_pilot_runs_use_one_sdk_client_and_one_loop(self):
        async def scenario(root: Path):
            loop_ids = []
            request_count = 0
            answer = json.dumps({"status": "NO_CONDITIONS_FOUND", "conditions": [],
                                 "logic_sections": [], "exceptions": [], "unresolved_relations": []})

            async def handler(request: httpx.Request) -> httpx.Response:
                nonlocal request_count
                loop_ids.append(id(asyncio.get_running_loop()))
                request_count += 1
                return httpx.Response(200, json={
                    "id": f"chatcmpl-{request_count}", "object": "chat.completion", "created": 1,
                    "model": "gpt-5.6-luna", "choices": [{"index": 0, "finish_reason": "stop",
                        "message": {"role": "assistant", "content": answer, "refusal": None}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                })

            ids = ["OFFLINE:1", "OFFLINE:2", "OFFLINE:3"]
            inputs = root / "inputs.jsonl"
            samples = root / "samples.jsonl"
            inputs.write_text("".join(json.dumps({"notice_id": nid, "raw_text": "offline fixture",
                "source_system": "BIZINFO", "completeness_status": "COMPLETE"}) + "\n" for nid in ids), encoding="utf-8")
            samples.write_text("".join(json.dumps({"notice_id": nid, "split": "DEVELOPMENT"}) + "\n" for nid in ids), encoding="utf-8")
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            provider = llm.OpenAIDirectProvider(api_key="offline-test-key", model="gpt-5.6-luna",
                                                http_client=client)
            budget = llm.RequestBudget(limit=3)
            loop_id = id(asyncio.get_running_loop())
            try:
                for index, notice_id in enumerate(ids):
                    report = await llm.run_pilot(provider, [notice_id], output_dir=root / f"out_{index}",
                        input_path=inputs, sample_path=samples, request_budget=budget, max_format_attempts=1)
                    self.assertEqual(report["status_counts"], {"COMPLETED": 1})
                    raw = llm._read_jsonl(root / f"out_{index}/raw_llm_responses.jsonl")
                    self.assertEqual(raw[0]["request_ordinal"], index + 1)
                    self.assertFalse(provider.client.is_closed())
            finally:
                await provider.aclose()
            self.assertEqual(request_count, 3)
            self.assertEqual(loop_ids, [loop_id] * 3)
            self.assertTrue(provider.client.is_closed())

        with tempfile.TemporaryDirectory() as temp:
            asyncio.run(scenario(Path(temp)))

    def test_three_sequential_sdk_requests_share_one_loop_and_close_once(self):
        async def scenario():
            loop_ids = []
            request_count = 0

            async def handler(request: httpx.Request) -> httpx.Response:
                nonlocal request_count
                loop_ids.append(id(asyncio.get_running_loop()))
                request_count += 1
                return httpx.Response(200, json={
                    "id": f"chatcmpl-{request_count}", "object": "chat.completion", "created": 1,
                    "model": "gpt-5.6-luna", "choices": [{"index": 0, "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "{}", "refusal": None}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                })

            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            provider = llm.OpenAIDirectProvider(api_key="offline-test-key", model="gpt-5.6-luna",
                                                http_client=client)
            close = provider.client.close
            close_count = 0

            async def counted_close():
                nonlocal close_count
                close_count += 1
                await close()

            provider.client.close = counted_close
            loop_id = id(asyncio.get_running_loop())
            for _ in range(3):
                result = await provider.generate([{"role": "user", "content": "offline"}])
                self.assertEqual(result.metadata["http_status"], 200)
                self.assertFalse(provider.client.is_closed())
            self.assertEqual(request_count, 3)
            self.assertEqual(loop_ids, [loop_id] * 3)
            await provider.aclose()
            await provider.aclose()
            self.assertEqual(close_count, 1)
            self.assertTrue(provider.client.is_closed())

        asyncio.run(scenario())

    def test_exception_path_context_manager_closes_client(self):
        async def scenario():
            async def handler(request: httpx.Request) -> httpx.Response:
                raise RuntimeError("synthetic transport failure")

            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            provider = llm.OpenAIDirectProvider(api_key="offline-test-key", model="gpt-5.6-luna",
                                                http_client=client)
            try:
                async with provider:
                    with self.assertRaises(Exception):
                        await provider.generate([{"role": "user", "content": "offline"}])
            finally:
                self.assertTrue(provider.client.is_closed())
                self.assertEqual(provider.last_error.get("diagnostic_code"), "UNKNOWN_RUNTIME_ERROR")

        asyncio.run(scenario())

    def test_closed_sdk_client_failure_gets_safe_diagnostic_code_only(self):
        async def scenario():
            client = httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"choices": []})))
            provider = llm.OpenAIDirectProvider(api_key="offline-test-key", model="gpt-5.6-luna",
                                                http_client=client)
            await provider.aclose()
            with self.assertRaises(Exception):
                await provider.generate([{"role": "user", "content": "offline"}])
            self.assertEqual(provider.last_error.get("diagnostic_code"), "HTTP_CLIENT_CLOSED")
            self.assertNotIn("exception_message", provider.last_error)
            self.assertNotIn("raw_exception", provider.last_error)

        asyncio.run(scenario())

    def test_request_budget_exposes_actual_reserved_ordinal(self):
        budget = llm.RequestBudget(limit=2)
        self.assertTrue(budget.consume())
        self.assertEqual(budget.last_request_ordinal, 1)
        self.assertTrue(budget.consume())
        self.assertEqual(budget.last_request_ordinal, 2)
        self.assertFalse(budget.consume())

    def test_run_remaining_uses_one_asyncio_run_for_batch(self):
        source = (runner.ROOT / "tools/run_condition_llm_openai_pilot_r2_norm_v2.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("asyncio.run(llm.run_pilot"), 0)
        self.assertIn("await llm.run_pilot(provider, [notice_id]", source)
        self.assertIn("finally:\n        await provider.aclose()", source)

    def test_live_execution_requires_both_run_and_api_authorization(self):
        with patch("sys.argv", ["recovery", "--run-recovery"]), self.assertRaises(SystemExit) as exc:
            from tools import run_condition_llm_openai_pilot_r2_norm_v2_recovery as recovery
            recovery.main()
        self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
