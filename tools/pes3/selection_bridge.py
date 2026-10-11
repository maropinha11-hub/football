#!/usr/bin/env python3
"""Join verified PES decisions with the native source catalogue and contract.

This is an automatic evidence index, not a runtime clip importer. A native
command remains an independent input; no PES number is cast to e_FunctionType.
The source candidate filter covers type/state only, not runtime feasibility.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from catalogue import build_catalogue
from selection_abi import Input, Decision


def digest(data): return hashlib.sha256(data).hexdigest()


RULES = {
    'ball_amplitude_limit': {'clip': 61, 'start_frame': 0, 'refresh_window': 4,
        'condition': 'state_flags bit 0 && player_id == context_player && ball_amplitude < 5888 - 12 * attribute_124',
        'change_call': '0x01879144', 'exclusive_branch': True},
    'chase_amplitude_limit': {'clip': 61, 'start_frame': 0, 'refresh_window': 4,
        'condition': 'outside ball branch && (direction_mask == 0 || chase_gate) && min(chase_amplitude, initial_amplitude) < signed_wrap32(initial_amplitude * 7) / 10',
        'change_call': '0x018791e4', 'exclusive_branch': True},
    'slow_or_turn_restart': {'clip': 47, 'start_frame': 5, 'refresh_window': 4,
        'condition': 'common branch && ((phase_130 == 0 && current_amplitude < 1024) || shortest_heading_separation / 256 >= 80)',
        'change_call': '0x01879248', 'substate_after': 55,
        'amplitude_reset_condition': 'shortest_heading_separation / 256 >= 80'},
}


def decision_rule(value, decision):
    """Attribute an observed decision to its already recovered branch."""
    if not decision.change_clip: return 'no_change'
    if (value.state_flags & 1) and value.player_id == value.context_player:
        role = 'ball_amplitude_limit'
    elif decision.requested_clip == 61:
        role = 'chase_amplitude_limit'
    else:
        role = 'slow_or_turn_restart'
    rule = RULES[role]
    if (decision.requested_clip, decision.start_frame, decision.refresh_window) != (
            rule['clip'], rule['start_frame'], rule['refresh_window']):
        raise ValueError('observed decision does not match the recovered rule')
    return role


def native_types(repo):
    """Read enum values and string mappings from this repository, not PES."""
    enum = (repo / 'src/gamedefines.hpp').read_text()
    block = re.search(r'enum e_FunctionType\s*\{([^}]+)\}', enum)
    if not block: raise ValueError('native function enum missing')
    names = re.findall(r'e_FunctionType_(\w+)', block.group(1))
    if len(names) != 15 or '=' in block.group(1): raise ValueError('unexpected native enum layout')
    source = (repo / 'src/gamedefines.cpp').read_text()
    start = source.index('e_FunctionType StringToFunctionType(')
    stop = source.index('\n}', start)
    strings = {name: kind for kind, name in re.findall(
        r'fun\.compare\("(\w+)"\) == 0\) return e_FunctionType_(\w+)', source[start:stop])}
    return [{'name': name, 'enum': index, 'source_type': strings.get(name),
             'query_type': 'shortpass' if name == 'LongPass' else strings.get(name)}
            for index, name in enumerate(names)]


def source_candidates(catalogue, query_type, special='', retain='', specialvar1=0.0, specialvar2=0.0):
    """Only the authored type/property subset of CrudeSelection; no ranking."""
    result = []
    for animation in catalogue['animations']:
        if animation['runtime_load_policy'] != 'loaded_and_mirrored' or animation['type'] != query_type:
            continue
        p = animation['properties']
        if p.get('incoming_special_state', '') != special: continue
        incoming = p.get('incoming_retain_state', '')
        if (query_type == 'deflect' or bool(retain) != bool(incoming)) and incoming != retain: continue
        if float(p.get('specialvar1') or 0) != specialvar1 or float(p.get('specialvar2') or 0) != specialvar2: continue
        result.append(animation['path'])
    return result


def build(repo, selection, action_index):
    report = json.loads((selection / 'selection-validation.json').read_text())
    raw = (selection / 'selection-vectors.json').read_bytes()
    if report['result'] != 'passed' or digest(raw) != report['files_sha256']['selection-vectors.json']:
        raise ValueError('selection evidence missing or changed')
    vectors = json.loads(raw)
    if vectors['state_sha256'] != report['state_sha256'] or len(vectors['cases']) != report['comparisons']:
        raise ValueError('selection report and vectors differ')
    for name in ('verify_selection.py', 'selection_abi.py'):
        if digest(Path(__file__).with_name(name).read_bytes()) != report['tool_sha256'][name]:
            raise ValueError('selection tool differs from the verified run')
    header = Path(__file__).with_name('recovered') / 'locomotion_selection.hpp'
    if digest(header.read_bytes()) != report['files_sha256'][header.name]:
        raise ValueError('semantic selection header differs from the verified run')
    word_raw = (selection / 'selection-instruction-words.json').read_bytes()
    if digest(word_raw) != report['files_sha256']['selection-instruction-words.json']:
        raise ValueError('instruction evidence differs')
    words = json.loads(word_raw)
    for rule in RULES.values():
        if words.get(hex(int(rule['change_call'], 16))) != 0x0c459de8:
            raise ValueError('rule call site is not the original animation_change instruction')
    index_raw = action_index.read_bytes()
    index = json.loads(index_raw)
    if index['sources'] != report['sources']: raise ValueError('PES revision differs')
    if len(index['clips']) != 1105 or {c['clip'] for c in index['clips']} != set(range(1105)):
        raise ValueError('PES clip index is incomplete or duplicated')
    evidence, by_rule = [], Counter()
    for case in vectors['cases']:
        value = Input.from_buffer_copy(bytes.fromhex(case['input_hex']))
        decision = Decision.from_buffer_copy(bytes.fromhex(case['expected_hex']))
        rule = decision_rule(value, decision); by_rule[rule] += 1
        evidence.append({'id': case['id'], 'rule': rule,
            'clip': decision.requested_clip if decision.change_clip else None,
            'restart_frame_override': decision.frame_override if decision.writes & 1 else None,
            'memory_kind': case['memory_kind'], 'dependency_values': case['dependencies']})
    clips = []
    for old in index['clips']:
        verified = [name for name, rule in RULES.items() if rule['clip'] == old['clip']]
        clips.append({'clip': old['clip'], 'action_contexts': old['action_contexts'],
            'action1_substate_contexts': old['action1_substate_contexts'],
            'classification': old['classification'], 'semantic_name': None,
            'verified_common_locomotion_rules': verified,
            'rule_scope': {'action': 1, 'substate': 16} if verified else None,
            'native_animation_id': None, 'runtime_enabled': False})
    catalogue = build_catalogue(repo / 'data/media/animations')
    if catalogue['errors']: raise ValueError('native catalogue contains parse errors')
    actions = native_types(repo)
    for action in actions:
        candidates = source_candidates(catalogue, action['query_type'])
        action.update({'authored_candidates_empty_state': candidates,
            'authored_candidate_count': len(candidates), 'pes_request': None,
            'scope': 'Type/property subset, empty special/retain state, zero specialvar1/2. Generated/mirrored clips, velocity, direction, foot, lastditch, trip, reach and touch checks not included.'})
    anchors = {'src/gamedefines.hpp': 'enum e_FunctionType', 'src/gamedefines.cpp': 'e_FunctionType StringToFunctionType(',
        'src/onthepitch/player/humanoid/animcollection.cpp': 'void AnimCollection::CrudeSelection(',
        'src/onthepitch/player/humanoid/humanoid.cpp': 'bool Humanoid::SelectAnim('}
    sources = []
    for path, anchor in anchors.items():
        data = (repo / path).read_bytes(); text = data.decode()
        line = text[:text.index(anchor)].count('\n') + 1
        sources.append({'path': path, 'sha256': digest(data), 'anchor': anchor, 'line': line})
    return {'schema_version': 1, 'kind': 'selection_evidence_and_native_contract',
        'selection_run_id': report['run_id'], 'selection_report_sha256': digest((selection / 'selection-validation.json').read_bytes()),
        'action_index_sha256': digest(index_raw), 'state_sha256': report['state_sha256'],
        'rules': RULES, 'evidence': evidence, 'evidence_by_rule': dict(by_rule), 'clips': clips,
        'native_sources': sources, 'native_catalogue': catalogue, 'native_actions': actions,
        'tool_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
            ('selection_bridge.py', 'catalogue.py', 'selection_abi.py')},
        'runtime_enabled': False,
        'adapter_contract': {
            'native_command': 'Independent PlayerCommand.desiredFunctionType; never cast PES request/action/clip.',
            'numeric_selector': 'Owned Input -> Decision; helper predictions/predicates are explicit PES-unit inputs.',
            'numeric_speed': 'Owned SpeedInput -> integer amplitude. Zero target skips update.',
            'amplitudes_and_time': 'PES integer amplitude/frame/configuration units require verified conversion to native metres, seconds and 10 ms steps.',
            'pose': 'Requires verified 19-to-13-bone retarget, side/bind/axes/scale before native Animation insertion.',
            'contact': 'Keep native GetBestCheatableAnimID feasibility and FootballAnimationExtension contact timing; PES foot/head contact metadata not recovered.',
            'native_candidates': 'The catalogue offers source candidates and compatibility requirements, not final runtime ranking.',
            'fallback': 'Approved native selector remains active until a full imported clip/transition is validated.'},
        'scope': 'Automatic association of original decisions with their recovered conditions and catalogue contract. No manually guessed PES labels, PES/native ID equality, enabled clip import, final native selection, complete action, PS2 frame or gameplay equivalence.'}


def main():
    parser = argparse.ArgumentParser(description='Gerar mapa de condições PES e contrato do seletor nativo')
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--actions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.repo, args.selection, args.actions)
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({'clips': len(result['clips']), 'rules': len(result['rules']),
        'evidence_by_rule': result['evidence_by_rule'], 'native_files': result['native_catalogue']['animation_count'],
        'runtime_enabled': result['runtime_enabled']}, indent=2))


if __name__ == '__main__': main()
