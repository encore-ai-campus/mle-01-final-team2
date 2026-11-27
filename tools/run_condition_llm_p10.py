"""Offline P10 replay and remaining-three continuation using the P8 engine."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None
from tools import run_condition_llm_openai_pilot_r2_norm_v2_p8 as engine
from tools import run_condition_llm_openai_pilot_r2_norm_v2 as base
from tools import extract_condition_candidates_llm as llm
from tools import replay_condition_llm_attribute_normalization as replay

SOURCE = engine.RUN_DIR
SOURCE_RUN_ID = engine.RUN_ID
RUN_ID = 'llm_pilot_2_5c3_r2_norm_v2_p10'
OUT = base.DEV / RUN_ID
CLAIM = base.DEV / '.llm_pilot_2_5c3_r2_p10_claim.json'

def fingerprint():
    ledger = base.read_json(SOURCE / 'request_ledger.json')
    manifest = base.read_json(SOURCE / 'manifest.json')
    if ledger['used'] != 10 or ledger['limit'] != 13 or manifest['status'] != 'P8_BLOCKED':
        raise RuntimeError('P10_SOURCE_STATE_CHANGED')
    ids, frozen = base.verify_14_fixed_checks()
    files = [SOURCE / 'manifest.json', SOURCE / 'request_ledger.json', base.PARENT_RAW,
             ROOT / 'tools/extract_condition_candidates_llm.py',
             ROOT / 'tools/run_condition_llm_openai_pilot_r2_norm_v2.py', Path(engine.__file__), Path(__file__)]
    files += [p for p in SOURCE.rglob('*') if p.is_file()]
    return {'run_id': RUN_ID, 'source_run_id': SOURCE_RUN_ID,
            'files': {p.relative_to(ROOT).as_posix(): base.digest(p) for p in sorted(set(files))},
            'pilot_notice_ids': ids, 'fixed_inputs': frozen,
            'prompt_sha256': hashlib.sha256(llm.system_prompt().encode()).hexdigest(),
            'normalization_rules_sha256': llm.ATTRIBUTE_NORMALIZATION_RULES_SHA256,
            'settings': base.read_json(base.PARENT_MANIFEST)['fingerprint'],
            'limit': 13, 'inherited_used': 10}

def prepare():
    with base.successor_lock():
        fp = fingerprint()
        if (OUT / 'manifest.json').exists():
            if base.read_json(OUT / 'manifest.json')['fingerprint'] != fp:
                raise RuntimeError('P10_FINGERPRINT_CHANGED')
            return base.read_json(OUT / 'comparison_report.json')
        if OUT.exists() and any(OUT.iterdir()):
            raise RuntimeError('P10_OUTPUT_EXISTS')
        ids = fp['pilot_notice_ids']
        comparisons = []
        for i in range(7):
            target = OUT / ('lead_replay_v2' if i == 0 else f'notice_{i:02d}/attribute_replay_v2')
            old_replay = SOURCE / ('lead_replay_v2' if i == 0 else f'notice_{i:02d}/attribute_replay_v2')
            raw = base.PARENT_RAW if i == 0 else SOURCE / f'notice_{i:02d}/raw_llm_responses.jsonl'
            if i:
                # Keep original API/validation records; deterministic logic records are replayed separately.
                dest = OUT / f'notice_{i:02d}'
                dest.mkdir(parents=True, exist_ok=True)
                for p in (SOURCE / f'notice_{i:02d}').iterdir():
                    if p.is_file() and p.name != 'technical_gate.json':
                        shutil.copy2(p, dest / p.name)
            report = replay.replay(raw, target)
            old_candidates = llm._read_jsonl(old_replay / 'predictions_after_validation.jsonl')
            new_candidates = llm._read_jsonl(target / 'predictions_after_validation.jsonl')
            if old_candidates != new_candidates:
                raise RuntimeError('P10_CANDIDATE_CHANGED:' + ids[i])
            gate = (base.tech_gate_for_replay_only(report, target) if i == 0 else
                    base.tech_gate_for_notice(target.parent, report))
            if gate['status'] != 'PASS':
                raise RuntimeError('P10_REPLAY_GATE_FAILED:' + ids[i])
            base.write_json_atomic((target if i == 0 else target.parent) / 'technical_gate.json', gate)
            changed = [p.name for p in target.iterdir() if p.is_file() and (old_replay / p.name).exists()
                       and base.digest(p) != base.digest(old_replay / p.name)]
            comparisons.append({'notice_id': ids[i], 'proposal_count': report['proposal_count'],
                'accepted': report['accepted_unreviewed_count'], 'held': report['held_for_review_count'],
                'rejected': report['rejected_count'], 'candidates_identical': True,
                'gate': gate, 'changed_files': sorted(changed)})
        ledger = copy.deepcopy(base.read_json(SOURCE / 'request_ledger.json'))
        ledger['prior_p8_attempts'] = ledger['p8_attempts']
        ledger['p8_attempts'] = []
        ledger['lineage']['p10_source_ledger_sha256'] = base.digest(SOURCE / 'request_ledger.json')
        ledger['lineage']['p10_new_budget_granted'] = 0
        ledger['lineage']['p10_allowed_ordinals'] = [11, 12, 13]
        base.write_json_atomic(OUT / 'request_ledger.json', ledger)
        claim = {'run_id': RUN_ID, 'source_ledger_sha256': base.digest(SOURCE / 'request_ledger.json'),
                 'fingerprint_sha256': hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()}
        base.claim_single_successor(CLAIM, claim)
        manifest = {'run_id': RUN_ID, 'status': 'PREPARED_NO_API_CALLS', 'fingerprint': fp,
            'request_limit': 13, 'cumulative_used': 10, 'remaining_request_count': 3, 'api_call_count': 0,
            'prepared_unexecuted_notice_ids': ids[7:], 'current_unexecuted_notice_ids': ids[7:],
            'current_response_notice_ids': ids[:7], 'current_technical_pass_notice_ids': ids[:7],
            'current_technical_blocked_notice_ids': [], 'current_api_failure_notice_ids': [],
            'decision_eligible': False}
        base.write_json_atomic(OUT / 'manifest.json', manifest)
        result = {'status': 'PREPARED_NO_API_CALLS', 'api_call_count': 0, 'responses_reused': 7,
                  'requests_used': 10, 'request_limit': 13, 'remaining': 3, 'comparison': comparisons}
        base.write_json_atomic(OUT / 'comparison_report.json', result)
        return result

@contextmanager
def configured_engine():
    # Reuse the sequential SDK lifecycle, gate, budget lock, and strict evaluation implementation.
    with patch.multiple(engine, RUN_ID=RUN_ID, RUN_DIR=OUT, ALREADY_USED=10,
                        P8_MAX_REQUESTS=3, START_INDEX=7, CLAIM_PATH=CLAIM,
                        build_fingerprint=fingerprint):
        yield

def refresh_code_fingerprint():
    """Record a code-only preparation revision without changing the budget ledger."""
    with base.successor_lock():
        path = OUT / 'manifest.json'
        manifest = base.read_json(path)
        ledger = base.read_json(OUT / 'request_ledger.json')
        old = manifest['fingerprint']
        current = fingerprint()
        allowed = {'tools/run_condition_llm_p10.py',
                   'tools/run_condition_llm_openai_pilot_r2_norm_v2_p8.py'}
        if manifest['status'] != 'PREPARED_NO_API_CALLS' or ledger['used'] != 10 or ledger['p8_attempts']:
            raise RuntimeError('P10_CODE_REVISION_REQUIRES_UNSTARTED_RUN')
        if {k:v for k,v in old.items() if k != 'files'} != {k:v for k,v in current.items() if k != 'files'}:
            raise RuntimeError('P10_NON_CODE_FINGERPRINT_CHANGE')
        changed = {k for k in set(old['files']) | set(current['files'])
                   if old['files'].get(k) != current['files'].get(k)}
        if not changed.issubset(allowed):
            raise RuntimeError('P10_UNAPPROVED_FINGERPRINT_CHANGE:' + ','.join(sorted(changed)))
        claim = base.read_json(CLAIM)
        old_hash = hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
        if claim.get('fingerprint_sha256') != old_hash:
            raise RuntimeError('P10_EXISTING_CLAIM_MISMATCH')
        if not changed:
            return {'status':'FINGERPRINT_UNCHANGED'}
        archive = OUT / 'fingerprint_history' / base.digest(path)
        archive.mkdir(parents=True, exist_ok=False)
        shutil.copy2(path, archive / 'manifest.json')
        shutil.copy2(CLAIM, archive / 'claim.json')
        revision = {'reason':'FIX_SOURCE_RUN_ID_DURING_ENGINE_CONFIGURATION',
                    'changed_code_files': sorted(changed), 'previous_fingerprint_sha256':old_hash,
                    'ledger_sha256':base.digest(OUT / 'request_ledger.json')}
        base.write_json_atomic(archive / 'revision.json', revision)
        manifest['fingerprint'] = current
        manifest['code_revision'] = revision
        claim['fingerprint_sha256'] = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
        base.write_json_atomic(path, manifest)
        base.write_json_atomic(CLAIM, claim)
        return {'status':'CODE_FINGERPRINT_REVISED', **revision}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--run-remaining', action='store_true')
    modes.add_argument('--evaluate', action='store_true')
    modes.add_argument('--refresh-code-fingerprint', action='store_true')
    modes.add_argument('--check-execution', action='store_true')
    p.add_argument('--authorize-api', action='store_true')
    p.add_argument('--env-file', type=Path, default=ROOT / '.env')
    args = p.parse_args()
    if args.run_remaining and not args.authorize_api:
        p.error('--run-remaining requires --authorize-api')
    if args.prepare:
        result = prepare()
    elif args.refresh_code_fingerprint:
        result = refresh_code_fingerprint()
    else:
        with configured_engine():
            result = (engine.run_remaining(args.env_file, check_only=args.check_execution)
                      if args.run_remaining or args.check_execution else engine.evaluate())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
