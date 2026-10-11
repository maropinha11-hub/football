from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/pes3'))
from catalogue import build_catalogue
from selection_abi import Input, Decision
from selection_bridge import decision_rule, native_types, source_candidates


class SelectionBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.catalogue = build_catalogue(cls.repo / 'data/media/animations')

    def test_native_header_has_no_direct_type_and_longpass_uses_shortpass(self):
        types = {a['name']: a for a in native_types(self.repo)}
        self.assertEqual(types['LongPass']['enum'], 5)
        self.assertEqual(types['LongPass']['query_type'], 'shortpass')
        self.assertIsNone(types['Header']['query_type'])
        self.assertEqual(source_candidates(self.catalogue, None), [])

    def test_real_movement_candidates_exclude_templates_and_incompatible_states(self):
        paths = source_candidates(self.catalogue, 'movement')
        by_path = {a['path']: a for a in self.catalogue['animations']}
        self.assertGreater(len(paths), 0)
        for path in paths:
            a = by_path[path]
            self.assertEqual(a['runtime_load_policy'], 'loaded_and_mirrored')
            self.assertFalse(a['properties'].get('incoming_special_state'))
            self.assertFalse(a['properties'].get('incoming_retain_state'))
        special = source_candidates(self.catalogue, 'movement', special='lay_back')
        self.assertGreater(len(special), 0)
        self.assertFalse(set(paths) & set(special))

    def test_native_retain_hand_switch_is_lenient_except_for_deflect(self):
        animation = {'path': 'case.anim', 'runtime_load_policy': 'loaded_and_mirrored', 'type': 'movement',
                     'properties': {'incoming_retain_state': 'left_hand'}}
        catalogue = {'animations': [animation]}
        self.assertEqual(source_candidates(catalogue, 'movement', retain='right_hand'), ['case.anim'])
        animation['type'] = 'deflect'
        self.assertEqual(source_candidates(catalogue, 'deflect', retain='right_hand'), [])

    def test_common_rule_keeps_branch_and_rejects_wrong_frame(self):
        value = Input(state_flags=1, player_id=10, context_player=10)
        decision = Decision(change_clip=1, requested_clip=61, start_frame=0, refresh_window=4)
        self.assertEqual(decision_rule(value, decision), 'ball_amplitude_limit')
        value.state_flags = 0
        self.assertEqual(decision_rule(value, decision), 'chase_amplitude_limit')
        decision.start_frame = 5
        with self.assertRaises(ValueError): decision_rule(value, decision)


if __name__ == '__main__': unittest.main()
