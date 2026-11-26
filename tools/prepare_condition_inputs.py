"""Build review-only condition inputs from a frozen normalized snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / 'data/normalized/v1/20261125_g2b'
FACTS = ROOT / 'data/normalized/20261124/notices_normalized.jsonl'
KS = ROOT / 'data/kstartup/processed/kstartup_conditions.jsonl'
OUT = ROOT / 'data/condition_inputs/v1/20261125'
SEED = 25112026
SOURCES = ('BIZINFO', 'KSTARTUP')
KINDS = {'ELIGIBILITY', 'EXCLUSION', 'PREFERENCE'}
PATTERNS = {k: re.compile(v) for k, v in {
    'and': r'그리고|및|동시에|모두', 'or': r'또는|혹은|중 하나',
    'not': r'제외|불가|제한|아닌 경우', 'exception': r'단,|다만|예외|제외한다',
    'range': r'이내|미만|이상|초과|부터.{0,20}까지',
    'region': r'지역|소재|사업장|본점', 'age': r'업력|창업.{0,8}년|대표자.{0,8}세',
    'preference': r'가점|우대|우선 선정',
}.items()}
REVIEW = {'review_status': 'UNREVIEWED', 'decision_eligible': False}


def rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path}:{number}: invalid JSON') from exc
            if not isinstance(row, dict):
                raise ValueError(f'{path}:{number}: expected object')
            yield row


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Missing or invalid identifier')
    return value


def emit(stream, row):
    stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')


def dump(path, values):
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        for value in values:
            emit(stream, value)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def compact(text):
    return ' '.join(text.split()) if isinstance(text, str) else ''


def candidate_ref(notice_id, fact, occurrence=0):
    """Stable semantic reference; occurrence disambiguates identical repeated facts."""
    identity = {'notice_id': notice_id, 'source_kind': fact.get('source_kind'),
        'section': fact.get('section'), 'source_field': fact.get('source_field'),
        'char_start': fact.get('char_start'), 'attribute': fact.get('attribute'),
        'kind': fact.get('kind'), 'rule_id': fact.get('rule_id'),
        'evidence_text': fact.get('evidence_text'), 'value': fact.get('value')}
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return canonical, f'{notice_id}:FACT:{hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]}:{occurrence}'


def run(out=OUT, *, snapshot=SNAP, facts_path=FACTS, ks_path=KS, seed=SEED, facts_label=None):
    out, snapshot = Path(out), Path(snapshot)
    facts_path, ks_path = Path(facts_path), Path(ks_path)
    facts_label = str(facts_label if facts_label is not None else facts_path)
    paths = {'notices': snapshot/'notices.jsonl', 'chunks': snapshot/'chunks.jsonl',
             'facts': facts_path, 'kstartup': ks_path}
    for path in paths.values():
        if path.parent.resolve() == out.resolve():
            raise ValueError('Output must not overwrite input directory')
    hashes = {key: sha256_file(path) for key, path in paths.items()}
    out.mkdir(parents=True, exist_ok=True)
    # Stage all artifacts before replacing any existing output.
    with tempfile.TemporaryDirectory(prefix='.condition-', dir=out) as tmp:
        stage = Path(tmp)
        eligible, seen, ks_snapshot, g2b_samples = {}, set(), set(), []
        deferred = g2b_count = 0
        with (stage/'deferred.tmp').open('w', encoding='utf-8', newline='\n') as stream:
            for n in rows(paths['notices']):
                nid = identifier(n['notice_id'])
                if nid in seen:
                    raise ValueError(f'Duplicate notice ID: {nid}')
                seen.add(nid)
                src = n['source']['source_system']
                t = n['condition_texts']['eligibility']
                text = t.get('text')
                if src == 'KSTARTUP':
                    ks_snapshot.add(nid)
                if src in SOURCES and t.get('availability') == 'PRESENT' and compact(text):
                    eligible[nid] = n
                    continue
                deferred += 1
                emit(stream, {'notice_id': nid, 'source_system': src, 'disposition': 'DEFERRED',
                              'reason': 'SOURCE_TEXT_UNAVAILABLE_OR_UNSUPPORTED',
                              'availability': t.get('availability'), **REVIEW})
                if src == 'G2B':
                    g2b_count += 1
                    if len(g2b_samples) < 4:
                        g2b_samples.append({'notice_id': nid, 'source_system': src,
                            'notice_type': n.get('notice_type'), 'source_id': n['source'].get('source_id'),
                            'reason': 'CONDITION_SOURCE_TEXT_NOT_COLLECTED' if t.get('availability') == 'NOT_COLLECTED' else 'SOURCE_TEXT_UNAVAILABLE_OR_UNSUPPORTED',
                            'availability_status': t.get('availability'), **REVIEW})
        facts, fact_seen = {}, set()
        for f in rows(facts_path):
            nid = identifier(f['notice_id'])
            if nid in fact_seen:
                raise ValueError(f'Duplicate legacy notice ID: {nid}')
            fact_seen.add(nid)
            if nid in eligible:
                facts[nid] = f
        ksc, ksids = Counter(), Counter()
        for c in rows(ks_path):
            aid = c.get('announcement_id')
            if aid is None or not str(aid).strip() or isinstance(aid, bool):
                raise ValueError('Missing K-Startup announcement ID')
            nid = 'KSTARTUP:' + str(aid)
            ksids[nid] += 1
            ksc.update(x.get('review_status', 'MISSING') for x in c.get('conditions', []))
        missing = sorted(ks_snapshot - ksids.keys())
        extra = sorted(ksids.keys() - ks_snapshot)
        chunks = defaultdict(list)
        chunk_seen = set()
        orphan_chunks = 0
        for c in rows(paths['chunks']):
            cid = identifier(c['chunk_id'])
            if cid in chunk_seen:
                raise ValueError(f'Duplicate chunk ID: {cid}')
            chunk_seen.add(cid)
            nid = c.get('notice_id')
            if nid not in seen:
                orphan_chunks += 1
            n = eligible.get(nid)
            if n is None or c.get('search_eligible') is not True or c.get('privacy_status') != 'CLEARED':
                continue
            origin = c.get('origin')
            if not isinstance(origin, str) or not origin.strip() or origin.upper().startswith('ATTACHMENT') or origin.upper() == 'UNKNOWN':
                continue
            if c.get('source_system') != n['source']['source_system']:
                continue
            if compact(n['condition_texts']['eligibility']['text']) in compact(c.get('text')):
                chunks[nid].append(cid)
        if orphan_chunks:
            raise ValueError(f'Orphan chunks: {orphan_chunks}')
        inputs, candidate_count, pattern = [], 0, Counter({key: 0 for key in PATTERNS})
        candidate_seen = set()
        with (stage/'candidate_refs.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
            for nid, n in sorted(eligible.items()):
                src = n['source']['source_system']
                text = n['condition_texts']['eligibility']['text']
                refs = [{'source_kind': 'NOTICE_FIELD', 'path': 'condition_texts.eligibility.text',
                         'text': text, 'chunk_ids': sorted(chunks[nid]), 'review_status': 'UNREVIEWED'}]
                local_refs = []
                for fact in facts.get(nid, {}).get('facts', []):
                    ev = fact.get('evidence_text')
                    if fact.get('kind') not in KINDS or not compact(ev):
                        continue
                    canonical, base_ref = candidate_ref(nid, fact)
                    # Multiplicity only distinguishes byte-for-byte identical repeated facts;
                    # the stable semantic digest is independent of input ordering.
                    occurrence = sum(1 for prior in candidate_seen if prior == canonical)
                    _, ref = candidate_ref(nid, fact, occurrence)
                    if ref in candidate_seen:
                        raise ValueError(f'Duplicate candidate reference: {ref}')
                    candidate_seen.add(canonical)
                    # Keep emitted reference uniqueness separate from identity records.
                    candidate_seen.add(ref)
                    local_refs.append(ref)
                    emit(stream, {'notice_id': nid, 'source_system': src, 'candidate_ref': ref,
                                  'legacy_candidate_ref': f'{nid}:{fact.get("attribute")}:{fact.get("char_start")}',
                                  'source_file': facts_label, 'source_field': fact.get('source_field'),
                                  'source_position': fact.get('char_start'), 'candidate_ordinal': occurrence,
                                  'attribute': fact.get('attribute'), 'kind': fact.get('kind'),
                                  'normalized_value': fact.get('value'), 'evidence_text': ev, 'review_status': 'UNREVIEWED',
                                  'source_kind': fact.get('source_kind'), 'section': fact.get('section')})
                    candidate_count += 1
                inputs.append({'notice_id': nid, 'source_system': src, 'notice_type': n.get('notice_type'),
                    'title': n.get('title'), 'source_snapshot': snapshot.name, 'input_status': 'EXTRACTABLE',
                    'raw_text': text, 'availability_status': 'AVAILABLE',
                    'completeness_status': 'UNKNOWN' if src == 'KSTARTUP' else 'PARTIAL',
                    **REVIEW, 'condition_type_hint': 'UNCLASSIFIED', 'evidence': refs,
                    'candidate_refs': local_refs, 'search_eligible': bool(refs[0]['chunk_ids']),
                    'reference_date': n.get('application_period', {}).get('start')})
                for label, regex in PATTERNS.items():
                    pattern[label] += bool(regex.search(text))
        rng = random.Random(seed)
        samples = []
        for src in SOURCES:
            pool = [i for i in inputs if i['source_system'] == src]
            if len(pool) < 50:
                raise ValueError(f'{src}: expected at least 50 extractable notices, got {len(pool)}')
            rng.shuffle(pool)
            for split, group in [('DEVELOPMENT', pool[:40]), ('EVALUATION', pool[40:50])]:
                samples.extend({'notice_id': i['notice_id'], 'source_system': src, 'split': split,
                                'seed': seed, 'raw_text': i['raw_text'], 'input_ref': i['notice_id'],
                                **REVIEW} for i in group)
        if len({s['notice_id'] for s in samples}) != 100 or len(inputs) + deferred != len(seen):
            raise RuntimeError('Output count or split invariant violated')
        dump(stage/'extraction_inputs.jsonl', inputs)
        with (stage/'dispositions.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
            for i in inputs:
                emit(stream, {'notice_id': i['notice_id'], 'source_system': i['source_system'],
                              'disposition': 'EXTRACTABLE', 'reason': 'ELIGIBILITY_SOURCE_TEXT_AVAILABLE', **REVIEW})
            for row in rows(stage/'deferred.tmp'):
                emit(stream, row)
        (stage/'deferred.tmp').unlink()
        dump(stage/'representative_samples.jsonl', samples)
        dump(stage/'g2b_deferred_samples.jsonl', g2b_samples)
        dump(stage/'kstartup_candidate_audit.jsonl', (
            {'notice_id': nid, 'candidate_rows': ksids[nid], 'in_snapshot': nid in ks_snapshot,
             'extractable': nid in eligible} for nid in sorted(ks_snapshot | ksids.keys())))
        report = {'seed': seed, 'snapshot': snapshot.name, 'counts': {
            'all': len(seen), 'extractable': len(inputs), 'deferred': deferred, 'g2b_deferred': g2b_count,
            'inputs_by_source': dict(Counter(i['source_system'] for i in inputs)), 'candidate_refs': candidate_count,
            'samples': dict(Counter(s['source_system']+':'+s['split'] for s in samples))},
            'kstartup_candidate_notices': len(ksids), 'kstartup_missing_ids': len(missing),
            'kstartup_missing_notice_ids': missing, 'kstartup_extra_notice_ids': extra,
            'kstartup_duplicate_ids': sum(v > 1 for v in ksids.values()),
            'kstartup_review_status_counts': dict(ksc), 'legacy_fact_rows': len(fact_seen),
            'pattern_notice_counts': dict(pattern), 'input_sha256': hashes['notices'],
            'input_sha256_by_file': hashes, 'all_decision_eligible': False}
        if any(sha256_file(path) != hashes[key] for key, path in paths.items()):
            raise RuntimeError('Input changed during processing')
        (stage/'analysis_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        # Each replacement is atomic, but the complete set is not a transaction.
        for path in sorted(stage.iterdir()):
            if path.name != 'analysis_report.json':
                path.replace(out/path.name)
        (stage/'analysis_report.json').replace(out/'analysis_report.json')
        return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, default=OUT)
    p.add_argument('--snapshot-dir', type=Path, default=SNAP)
    p.add_argument('--facts-path', type=Path, default=FACTS)
    p.add_argument('--kstartup-path', type=Path, default=KS)
    p.add_argument('--seed', type=int, default=SEED)
    args = p.parse_args()
    print(json.dumps(run(args.output_dir, snapshot=args.snapshot_dir, facts_path=args.facts_path,
                         ks_path=args.kstartup_path, seed=args.seed), ensure_ascii=False, indent=2))
