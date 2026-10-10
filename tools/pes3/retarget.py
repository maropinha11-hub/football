#!/usr/bin/env python3
"""Prepare explicit topology candidates; never enable an uncalibrated import."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from savestate import digest

PARENTS = [-1, 0, 1, 1, 2, 3, 4, 5, 0, 8, 8, 9, 10, 11, 12, 8, 15, 13, 14]
PAIRS = [-1, -1, 3, 2, 5, 4, 7, 6, -1, 10, 9, 12, 11, 14, 13, -1, -1, 18, 17]


def prepare(evidence, object_path):
    if evidence['parents'] != PARENTS or evidence['mirror_pairs'] != PAIRS:
        raise ValueError('hierarquia PES não corresponde às relações conferidas')
    data = object_path.read_bytes()
    tree, native = ET.fromstring(data), []
    def visit(node, parent):
        name = node.findtext('name')
        if not name or any(n['name'] == name for n in native):
            raise ValueError('nome de osso nativo ausente ou duplicado')
        values = {}
        for field, size in (('position', 3), ('rotation', 4)):
            raw = node.findtext(field)
            numbers = [float(n) for n in raw.split(',')] if raw else []
            if len(numbers) != size or not all(math.isfinite(n) for n in numbers):
                raise ValueError('referência nativa inválida')
            values[field] = numbers
        native.append({'name': name, 'parent': parent, 'bind_position_m': values['position'],
                       'bind_rotation_source': values['rotation']})
        for child in node.findall('node'): visit(child, name)
    for root in tree.findall('node'): visit(root, 'player')
    candidates = {'body': [0], 'middle': [8], 'neck': [16],
        'left_thigh': [2, 3], 'right_thigh': [3, 2], 'left_knee': [4, 5], 'right_knee': [5, 4],
        'left_ankle': [6, 7], 'right_ankle': [7, 6],
        'left_shoulder': [11, 12], 'right_shoulder': [12, 11], 'left_elbow': [13, 14], 'right_elbow': [14, 13]}
    if {n['name'] for n in native} != set(candidates):
        raise ValueError('esqueleto nativo fora dos 13 nós conferidos')
    def chain(index):
        path = [index]
        while PARENTS[path[0]] >= 0: path.insert(0, PARENTS[path[0]])
        return path
    for bone in native:
        bone['pes_candidates'] = [{'index': i, 'ancestor_chain': chain(i)} for i in candidates[bone['name']]]
    return {'schema_version': 1, 'state_sha256': evidence['state_sha256'],
        'native_object_sha256': digest(data), 'pes_parent_indices': PARENTS, 'pes_mirror_pairs': PAIRS,
        'mapping_status': 'topology_candidates', 'native_skeletal_nodes': len(native),
        'native_animation_channels': len(native) + 1, 'targets': native,
        'movement_channel': {'name': 'player', 'policy': 'native controller translation remains authoritative'},
        'runtime_enabled': False, 'axes_calibrated': False, 'scale_calibrated': False,
        'left_right_calibrated': False, 'ball_contacts_validated': False,
        'scope': 'Candidate correspondences from observed PES topology and native XML. Bone names are anatomical hypotheses, not recovered PES symbols. Parent frames must be composed; left/right, bind corrections, units and contact timing remain unverified.'}


def main():
    parser = argparse.ArgumentParser(description='Preparar relações de ossos para uma futura importação PES')
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--object', type=Path, default=Path(__file__).resolve().parents[2] / 'data/media/objects/players/player.object')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(json.loads(args.evidence.read_text()), args.object)
    with args.output.open('x') as stream: json.dump(plan, stream, indent=2); stream.write('\n')
    print('13 nós nativos; relações candidatas registradas, importação desabilitada.')


if __name__ == '__main__': main()
