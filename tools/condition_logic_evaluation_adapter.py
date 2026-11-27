"""Versioned, evaluation-only AST transport. No extraction or semantic inference."""
from __future__ import annotations
import copy
from collections import Counter

VERSION='condition-logic-evaluation-adapter-v1'
LOGICAL_OPERATORS={'AND','OR','NOT','UNRESOLVED'}

def tree_counts(roots):
    groups=edges=nested=refs=0
    def walk(node,depth=0):
        nonlocal groups,edges,nested,refs
        if node.get('node_type')=='CONDITION_REF':refs+=1;return
        if node.get('node_type')=='LOGICAL_GROUP':
            groups+=1;nested+=int(depth>0);edges+=len(node.get('children',[]))
            for child in node.get('children',[]):walk(child,depth+1)
    for root in roots:walk(root)
    return {'groups':groups,'edges':edges,'nested_groups':nested,'condition_reference_occurrences':refs,'root_count':len(roots)}

def adapt(record,conditions,proposal=None):
    """Return existing AST roots and a separate preservation/integrity audit.

    logic_sections.root is authoritative when present. v1 records without
    sections retain their original collection roots. Explicit GROUP_REFs can
    be inlined from an explicit groups registry; no parent/child is inferred.
    Unsupported exception/relation semantics are preserved in the audit only.
    """
    source=copy.deepcopy(record or {})
    proposal=copy.deepcopy(proposal or {})
    errors=[];warnings=[]
    def error(code,**info):errors.append({'code':code,**info})
    valid_ids=[r['condition_id'] for r in conditions]
    if len(valid_ids)!=len(set(valid_ids)):error('DUPLICATE_CONDITION_ID')
    valid=set(valid_ids)
    if 'logic_sections' in source:
        sections=source['logic_sections']
        roots=[]
        for index,section in enumerate(sections):
            if 'root' not in section:error('SECTION_ROOT_MISSING',section=index)
            else:roots.append(section['root'])
        selection='EXISTING_LOGIC_SECTIONS_ROOTS'
    else:
        roots=source.get('logical_roots')
        if roots is None:roots=[r for collection in source.get('condition_sets',{}).values() for r in collection.get('logical_roots',[])]
        sections=None;selection='EXISTING_V1_ROOTS_NO_INFERENCE'
    registry={};active_objects=set()
    def declare(node):
        if not isinstance(node,dict):error('INVALID_NODE');return
        if id(node) in active_objects:error('CYCLIC_INLINE_STRUCTURE');return
        active_objects.add(id(node))
        if node.get('node_type')=='LOGICAL_GROUP':
            gid=node.get('group_id')
            if not gid:error('MISSING_GROUP_ID')
            elif gid in registry:error('DUPLICATE_GROUP_ID',group_id=gid)
            else:registry[gid]=node
            for child in node.get('children',[]):declare(child)
        active_objects.remove(id(node))
    for root in roots:declare(root)
    groups=source.get('groups',[])
    if isinstance(groups,dict):groups=list(groups.values())
    for group in groups:declare(group)
    used_groups=set()
    def expand(node,stack=()):
        if not isinstance(node,dict):return None
        kind=node.get('node_type')
        if kind=='CONDITION_REF':
            if node.get('condition_id') not in valid:error('UNKNOWN_CONDITION_REF',condition_id=node.get('condition_id'))
            return copy.deepcopy(node)
        if kind=='GROUP_REF':
            gid=node.get('group_id')
            if gid not in registry:error('UNKNOWN_GROUP_REF',group_id=gid);return None
            return expand(registry[gid],stack)
        if kind!='LOGICAL_GROUP':error('UNSUPPORTED_NODE_TYPE',node_type=kind);return None
        gid=node.get('group_id')
        if gid in stack:error('CYCLIC_GROUP_REF',group_id=gid);return None
        used_groups.add(gid)
        op=node.get('operator');children=node.get('children')
        if op not in LOGICAL_OPERATORS:error('INVALID_LOGIC_OPERATOR',group_id=gid)
        if not isinstance(children,list) or not children:
            error('MISSING_PARENT_CHILD_RELATION',group_id=gid);return None
        if (op in {'AND','OR'} and len(children)<2) or (op=='NOT' and len(children)!=1):error('INVALID_LOGIC_ARITY',group_id=gid)
        signatures=[(c.get('node_type'),c.get('condition_id',c.get('group_id'))) for c in children if isinstance(c,dict)]
        if len(signatures)!=len(set(signatures)):error('DUPLICATE_CHILD_REFERENCE',group_id=gid)
        expanded=[expand(child,stack+(gid,)) for child in children]
        if any(child is None for child in expanded):return None
        result=copy.deepcopy(node);result['children']=expanded
        return result
    expanded=[expand(root) for root in roots]
    for gid in set(registry)-used_groups:error('UNREFERENCED_GROUP',group_id=gid)
    mapping={int(k):v for k,v in proposal.get('index_to_condition_id',{}).items()}
    for index,cid in mapping.items():
        if cid not in valid:error('PROPOSAL_MAP_UNKNOWN_CONDITION',proposal_index=index,condition_id=cid)
    states=proposal.get('proposal_validation_states',{})
    unresolved=set(proposal.get('unresolved_condition_indexes',[]))
    missing={int(k) for k,v in states.items() if v!='ACCEPTED_UNREVIEWED'}
    if not missing.issubset(unresolved):error('MISSING_UNRESOLVED_PROPOSAL_REF',missing_indexes=sorted(missing-unresolved))
    if unresolved and proposal.get('logical_completeness')!='INCOMPLETE':error('INCOMPLETE_LOGIC_PROMOTED')
    if proposal.get('invalid_reference_indexes'):error('INVALID_PROPOSAL_INDEX',indexes=proposal['invalid_reference_indexes'])
    exception_audit=[]
    resolutions=proposal.get('exception_resolution',[])
    for index,exception in enumerate(proposal.get('exceptions',[])):
        targets=exception.get('target_condition_indexes',[])
        target_missing=sorted(set(targets)-set(mapping))
        resolution=resolutions[index] if index<len(resolutions) else None
        if target_missing and not set(target_missing).issubset(unresolved):error('EXCEPTION_TARGET_UNRESOLVED_REF_MISSING',exception_index=index)
        if resolution and (resolution.get('original_exception')!=exception or resolution.get('original_target_condition_indexes')!=targets):
            error('EXCEPTION_TARGET_OR_SCOPE_CHANGED',exception_index=index)
        if target_missing and (not resolution or resolution.get('application_allowed') is not False):
            error('UNRESOLVED_EXCEPTION_APPLICATION_NOT_BLOCKED',exception_index=index)
        exception_audit.append({'original_exception':exception,'original_target_indexes':targets,
            'validated_target_condition_ids':[mapping[t] for t in targets if t in mapping],
            'unresolved_target_indexes':target_missing,'resolution':resolution,
            'semantic_evaluation_status':'NOT_MEASURED_UNSUPPORTED'})
    relations=proposal.get('unresolved_relations',[])
    relation_audit=[{'original':r,'validated_condition_ids':[mapping[i] for i in r.get('condition_indexes',[]) if i in mapping],
        'unresolved_indexes':[i for i in r.get('condition_indexes',[]) if i not in mapping],
        'semantic_evaluation_status':'NOT_MEASURED_UNSUPPORTED'} for r in relations]
    # Groups with no surviving targets remain source proposals, never executable ASTs.
    unexecutable=[copy.deepcopy(g) for g in proposal.get('logic_sections',[])
                  if g.get('condition_indexes') and not any(i in mapping for i in g['condition_indexes'])]
    if errors:
        evaluation={}
    elif source:
        evaluation=copy.deepcopy(source)
        evaluation['logical_roots']=expanded
        evaluation['decision_eligible']=False
        # No new semantic adapter for exceptions/effects/relations is introduced.
    else:evaluation={}
    audit={'adapter_version':VERSION,'root_selection':selection,'integrity_status':'ERROR' if errors else 'PASS',
        'errors':errors,'warnings':warnings,'group_definitions':len(registry),'used_group_ids':sorted(g for g in used_groups if isinstance(g,str)),
        'source_sections':copy.deepcopy(sections),'source_roots':copy.deepcopy(roots),
        'evaluation_counts':tree_counts(expanded) if not errors else tree_counts([]),
        'source_proposal':proposal,'unresolved_condition_indexes':sorted(unresolved),
        'unexecutable_groups':unexecutable,'exceptions':exception_audit,'unresolved_relations':relation_audit,
        'logical_completeness':proposal.get('logical_completeness','NOT_AVAILABLE_IN_SOURCE'),
        'unsupported_semantics':{'exception_effects':'NOT_MEASURED_UNSUPPORTED',
            'exception_scope':'PRESERVED_NOT_SCORED','unresolved_relation_meaning':'NOT_MEASURED_UNSUPPORTED',
            'completeness':'PRESERVED_NOT_SCORED','phase_dependent_logic':'NOT_MEASURED_UNSUPPORTED'},
        'decision_eligible':False}
    return evaluation,audit
