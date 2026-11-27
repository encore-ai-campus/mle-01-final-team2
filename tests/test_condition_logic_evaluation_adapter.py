import copy
import unittest
from tools import condition_logic_evaluation_adapter as a
from tools import evaluate_condition_pipeline_v11 as v

def ref(cid):return {'node_type':'CONDITION_REF','condition_id':cid}
def group(gid,operator,children):
    return {'node_type':'LOGICAL_GROUP','group_id':gid,'operator':operator,'children':children,
            'review_status':'UNREVIEWED','evidence':None}
def record(roots):
    return {'notice_id':'SYNTHETIC','logic_sections':[{'section_id':f's{i}','root':root,
        'condition_type':'ELIGIBILITY','evaluation_phase':'APPLICATION','fulfillment_phase':'APPLICATION'} for i,root in enumerate(roots)]}
def conditions(*ids):return [{'condition_id':cid} for cid in ids]

class AdapterTests(unittest.TestCase):
    def exact(self,roots,cids):
        original=record(roots);before=copy.deepcopy(original)
        result,audit=a.adapt(original,conditions(*cids))
        self.assertEqual(audit['errors'],[])
        self.assertEqual(original,before)
        self.assertEqual(v._roots(result),roots)
        score=v.compare_logic(roots,v._roots(result))
        self.assertTrue(score['notice_structure_exact'])
        self.assertEqual(score['logical_relation']['fp'],0)
        self.assertEqual(score['logical_relation']['fn'],0)
        return score
    def test_single_and_exact(self):
        s=self.exact([group('g','AND',[ref('a'),ref('b')])],['a','b'])
        self.assertEqual(s['logical_relation']['tp'],2)
        self.assertEqual(s['logical_group_exact']['correct'],1)
    def test_single_or_exact(self):
        self.assertEqual(self.exact([group('g','OR',[ref('a'),ref('b')])],['a','b'])['logical_relation']['f1'],1)
    def test_multiple_roots_exact(self):
        score=self.exact([group('a','AND',[ref('x'),ref('y')]),group('b','OR',[ref('z'),ref('w')])],['x','y','z','w'])
        self.assertEqual(score['logical_group_exact']['correct'],2)
    def test_nested_exact(self):
        roots=[group('g','AND',[ref('a'),group('h','OR',[ref('b'),ref('c')])])]
        s=self.exact(roots,['a','b','c'])
        self.assertEqual(s['logical_group_exact']['correct'],2)
        self.assertEqual(s['logical_relation']['tp'],4)
    def test_shared_condition_across_groups_is_not_duplicate_definition(self):
        roots=[group('g','AND',[ref('a'),ref('b')]),group('h','OR',[ref('a'),ref('c')])]
        self.exact(roots,['a','b','c'])
    def test_flat_roots_are_not_guessed_as_nested(self):
        roots=[group('g','AND',[ref('a'),ref('b')]),group('h','OR',[ref('b'),ref('c')])]
        result,audit=a.adapt(record(roots),conditions('a','b','c'))
        self.assertEqual(v._roots(result),roots)
        self.assertEqual(audit['evaluation_counts']['nested_groups'],0)
    def test_exception_scope_and_unresolved_refs_preserved(self):
        exception={'target_condition_indexes':[1],'effect':'WAIVE_REQUIREMENT','effect_target':'조건b','precondition':'증명서 확인'}
        proposal={'index_to_condition_id':{0:'a'},'proposal_validation_states':{'0':'ACCEPTED_UNREVIEWED','1':'REJECTED'},
            'unresolved_condition_indexes':[1],'logical_completeness':'INCOMPLETE','exceptions':[exception],
            'exception_resolution':[{'original_exception':exception,'original_target_condition_indexes':[1],
                                     'application_allowed':False}],
            'unresolved_relations':[{'condition_indexes':[0,1],'reason':'불명확'}]}
        result,audit=a.adapt(record([group('g','UNRESOLVED',[ref('a')])]),conditions('a'),proposal)
        self.assertEqual(audit['errors'],[])
        self.assertEqual(audit['exceptions'][0]['unresolved_target_indexes'],[1])
        self.assertEqual(audit['exceptions'][0]['original_exception'],exception)
        self.assertEqual(audit['unresolved_relations'][0]['original'],proposal['unresolved_relations'][0])
        self.assertNotIn('gold_exceptions',result)
        self.assertNotIn('unresolved_relations',result)
        self.assertEqual(v._roots(result)[0]['operator'],'UNRESOLVED')
    def test_all_candidates_rejected_group_is_not_executable(self):
        proposal={'logic_sections':[{'condition_indexes':[0,1],'operator':'UNRESOLVED'}],
            'index_to_condition_id':{},'unresolved_condition_indexes':[0,1],
            'proposal_validation_states':{'0':'REJECTED','1':'HELD_FOR_REVIEW'},'logical_completeness':'INCOMPLETE'}
        result,audit=a.adapt({},[],proposal)
        self.assertEqual(result,{})
        self.assertEqual(len(audit['unexecutable_groups']),1)
        self.assertEqual(audit['evaluation_counts']['groups'],0)
    def test_no_group_not_inferred(self):
        result,audit=a.adapt({'logical_roots':[ref('a'),ref('b')]},conditions('a','b'))
        self.assertEqual(audit['evaluation_counts']['groups'],0)
        self.assertEqual(v._roots(result),[ref('a'),ref('b')])
    def test_missing_condition_ref_rejected(self):
        output,audit=a.adapt(record([group('g','AND',[ref('a'),ref('missing')])]),conditions('a'))
        self.assertEqual(output,{})
        self.assertIn('UNKNOWN_CONDITION_REF',[e['code'] for e in audit['errors']])
    def test_explicit_group_refs_inlined_without_inference(self):
        source={'logical_roots':[{'node_type':'GROUP_REF','group_id':'g'}],
                'groups':[group('g','AND',[ref('a'),{'node_type':'GROUP_REF','group_id':'h'}]),
                          group('h','OR',[ref('b'),ref('c')])]}
        result,audit=a.adapt(source,conditions('a','b','c'))
        self.assertEqual(audit['errors'],[])
        self.assertEqual(audit['evaluation_counts']['groups'],2)
        expected=[group('g','AND',[ref('a'),group('h','OR',[ref('b'),ref('c')])])]
        self.assertTrue(v.compare_logic(expected,v._roots(result))['notice_structure_exact'])
    def test_missing_group_reference_rejected(self):
        result,audit=a.adapt({'logical_roots':[{'node_type':'GROUP_REF','group_id':'missing'}]},[])
        self.assertEqual(result,{})
        self.assertIn('UNKNOWN_GROUP_REF',[e['code'] for e in audit['errors']])
    def test_cycle_rejected(self):
        source={'logical_roots':[{'node_type':'GROUP_REF','group_id':'a'}],
            'groups':[group('a','UNRESOLVED',[{'node_type':'GROUP_REF','group_id':'b'}]),
                      group('b','UNRESOLVED',[{'node_type':'GROUP_REF','group_id':'a'}])]}
        result,audit=a.adapt(source,[])
        self.assertEqual(result,{})
        self.assertIn('CYCLIC_GROUP_REF',[e['code'] for e in audit['errors']])
    def test_duplicate_group_id_rejected(self):
        output,audit=a.adapt(record([group('g','AND',[ref('a'),ref('b')]),group('g','OR',[ref('a'),ref('b')])]),conditions('a','b'))
        self.assertEqual(output,{})
        self.assertIn('DUPLICATE_GROUP_ID',[e['code'] for e in audit['errors']])
    def test_duplicate_child_reference_rejected(self):
        output,audit=a.adapt(record([group('g','AND',[ref('a'),ref('a')])]),conditions('a'))
        self.assertEqual(output,{})
        self.assertIn('DUPLICATE_CHILD_REFERENCE',[e['code'] for e in audit['errors']])
    def test_orphan_group_rejected(self):
        output,audit=a.adapt({'logical_roots':[ref('a')],'groups':[group('orphan','UNRESOLVED',[ref('a')])]},conditions('a'))
        self.assertEqual(output,{})
        self.assertIn('UNREFERENCED_GROUP',[e['code'] for e in audit['errors']])
    def test_missing_parent_child_relation_rejected(self):
        output,audit=a.adapt(record([group('g','AND',[])]),[])
        self.assertEqual(output,{})
        self.assertIn('MISSING_PARENT_CHILD_RELATION',[e['code'] for e in audit['errors']])
    def test_changed_ids_must_match_current_conditions(self):
        old=record([group('g','AND',[ref('old'),ref('b')])])
        _,audit=a.adapt(old,conditions('new','b'))
        self.assertTrue(audit['errors'])
        current=copy.deepcopy(old);current['logic_sections'][0]['root']['children'][0]=ref('new')
        output,audit=a.adapt(current,conditions('new','b'))
        self.assertEqual(audit['errors'],[])
        self.assertEqual(v._roots(output)[0]['children'][0]['condition_id'],'new')
    def test_missing_unresolved_and_exception_target_detected(self):
        proposal={'index_to_condition_id':{},'proposal_validation_states':{'0':'REJECTED'},
                  'unresolved_condition_indexes':[],'exceptions':[{'target_condition_indexes':[0]}]}
        _,audit=a.adapt({},[],proposal)
        codes={e['code'] for e in audit['errors']}
        self.assertIn('MISSING_UNRESOLVED_PROPOSAL_REF',codes)
        self.assertIn('EXCEPTION_TARGET_UNRESOLVED_REF_MISSING',codes)

if __name__=='__main__':unittest.main()
