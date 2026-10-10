#!/usr/bin/env python3
"""Recover routing and conservative animation call associations from SLES/OVER.

Routing tables are executable rewrites. Function summaries are static evidence,
not a replay of complete actions: ambiguous callees/arguments remain unresolved.
"""
import argparse
from collections import deque
import hashlib
import io
import importlib.util
import json
import struct
from pathlib import Path

from mips import Instruction, REGS

# The sibling CLI is named inspect.py; do not confuse it with stdlib inspect.
_spec = importlib.util.spec_from_file_location("pes3_binary_inspector", Path(__file__).with_name("inspect.py"))
_inspector = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_inspector)
read_afs, read_elf = _inspector.read_afs, _inspector.read_elf

ELF_SHA = "a3d39bf0f1d0030ccd4be17428d1dbdb7010e0b7a06ee545b5d614d378640b53"
OVER_SHA = "aa1942fd00fd60c7bdbedea766e94bbe6b7865593a4ca1479c89681e464166f3"
SINKS = {0x011677a0: "animation_change", 0x0119fc70: "blend_start", 0x018a4720: "phase_change"}
GP = 0x012adef0
MASK = (1 << 64) - 1


def sha(data): return hashlib.sha256(data).hexdigest()
def const(n): return frozenset({("constant", n & MASK)})
def pointer(kind, offset=0): return frozenset({(kind, offset)})
def integer(value):
    if value is not None and len(value) == 1:
        kind, number = next(iter(value))
        if kind == "constant": return number
    return None
def word(n):
    n &= 0xffffffff
    return (n - (1 << 32) if n & 0x80000000 else n) & MASK
def signed(n): return n - (1 << 64) if n & (1 << 63) else n
def describe(value):
    if value is None: return ["unresolved"]
    return [str(n) if kind == "constant" else f"{kind}:{n}" for kind, n in sorted(value)]
def join(a, b):
    if a is None or b is None: return None
    both = a | b
    return both if len(both) <= 64 else None


class Image:
    def __init__(self, elf, over):
        elf_data, over_data = Path(elf).read_bytes(), Path(over).read_bytes()
        if sha(elf_data) != ELF_SHA or sha(over_data) != OVER_SHA:
            raise ValueError("esta revisão exige os hashes SLES_519.12/OVER.AFS conferidos")
        metadata = read_elf(io.BytesIO(elf_data), len(elf_data))
        self.regions = [(s["virtual_address"], elf_data[s["offset"]:s["offset"]+s["file_size"]], "SLES_519.12")
                        for s in metadata["segments"] if s["type"] == 1 and s["file_size"]]
        entries, _ = read_afs(io.BytesIO(over_data), 0, len(over_data))
        entry = entries[6]
        game = over_data[entry["offset"]:entry["offset"]+entry["size"]]
        if game[:4] != b"MWo3" or b"game.ovl\0" not in game[:64]:
            raise ValueError("entrada 6 não é o módulo esperado")
        base = struct.unpack_from("<I", game, 8)[0]
        if base != 0x0163b800: raise ValueError("base de game.ovl divergente")
        self.regions.append((base, game, "OVER.AFS/6:game.ovl"))
        self.sources = [{"file": "SLES_519.12", "sha256": sha(elf_data), "bytes": len(elf_data)},
                        {"file": "OVER.AFS", "sha256": sha(over_data), "bytes": len(over_data)},
                        {"file": "game.ovl", "sha256": sha(game), "bytes": len(game), "base": hex(base)}]
        self.prologues = set()
        self.call_entries = set()
        for base, data, _ in self.regions:
            for offset in range(0, len(data)-3, 4):
                w = struct.unpack_from("<I", data, offset)[0]
                ins = Instruction(base+offset, w)
                if w >> 16 == 0x27bd and ins.simm < 0: self.prologues.add(ins.pc)
                if ins.op == 3: self.call_entries.add(ins.target)

    def read(self, address, size=4):
        matches = [(base, data, source) for base, data, source in self.regions
                   if base <= address and address+size <= base+len(data)]
        if len(matches) != 1: raise ValueError(f"endereço sem bytes únicos: {address:#x}")
        base, data, _ = matches[0]
        return data[address-base:address-base+size]

    def contains(self, address):
        return any(base <= address < base+len(data) for base, data, _ in self.regions)

    def instruction(self, address):
        if address & 3: raise ValueError("instrução desalinhada")
        return Instruction(address, struct.unpack("<I", self.read(address))[0])

    def bound(self, entry):
        base, data, _ = next(r for r in self.regions if r[0] <= entry < r[0]+len(r[1]))
        return min([base+len(data)] + [p for p in self.prologues if entry < p < base+len(data)])


def comparison_chain(image, start, end, selector_register):
    constants = {0: 0}
    cases = []
    for pc in range(start, end, 4):
        ins = image.instruction(pc)
        if ins.op in (9, 25) and ins.rs == 0: constants[ins.rt] = ins.simm & MASK
        elif ins.op == 4 and ins.rs != ins.rt and selector_register in (ins.rs, ins.rt):
            other = ins.rt if ins.rs == selector_register else ins.rs
            if other not in constants: raise ValueError(f"comparação não recuperada: {pc:#x}")
            cases.append({"value": constants[other], "branch_pc": hex(pc), "block": hex(ins.target)})
        elif ins.word and not (ins.conditional or ins.op == 0 and ins.fn == 45):
            raise ValueError(f"cadeia de comparação inesperada: {pc:#x}")
    if not cases or len({c["value"] for c in cases}) != len(cases):
        raise ValueError("cadeia de comparação inválida")
    return cases


def dispatchers(image):
    table = list(struct.unpack("<23I", image.read(0x018ec420, 23*4)))
    # Check the original range guard and table load, instead of trusting addresses.
    expected = [0x30a200ff, 0x2c410017, 0x3c03018f, 0x2463c420, 0x8c420000, 0x00400008]
    actual = [image.instruction(pc).word for pc in [0x0184f5c4,0x0184f5cc,0x0184f5e4,0x0184f5ec,0x0184f5f4,0x0184f5f8]]
    if actual != expected: raise ValueError("dispatcher de pedidos mudou")
    action = comparison_chain(image, 0x018807ec, 0x01880abc, 2)
    substates = comparison_chain(image, 0x01876b84, 0x01876c20, 3)
    action_handlers = []
    for case in action:
        at = int(case["block"], 16)
        entry = image.instruction(at)
        action_handlers.append(dict(case, handler=hex(entry.target) if entry.op==3 else None))
    # Default action 0 is checked as the last BEQ against zero.
    return {"requests": {"entry": "0x0184f5c0", "table": "0x018ec420", "mask": 255,
                          "targets": [hex(t) for t in table], "default": "0x01853d08"},
            "actions": {"function": "0x01880490", "entry": "0x018807ec", "field": "player+0xda:u8",
                        "cases": action_handlers, "default": "0x01880e5c"},
            "action1_substates": {"function": "0x01876b50", "entry": "0x01876b80",
                                  "field": "player+0xdc:u16", "cases": substates, "default": "0x01876c20"}}


def operation(left, right, kind):
    if left is None or right is None: return None
    values = set()
    for lk, l in left:
        for rk, r in right:
            if lk == rk == "constant":
                if kind == "add32": v = word(l+r)
                elif kind == "sub32": v = word(l-r)
                elif kind == "add": v = (l+r) & MASK
                elif kind == "sub": v = (l-r) & MASK
                elif kind == "and": v = l&r
                elif kind == "or": v = l|r
                elif kind == "xor": v = l^r
                elif kind == "slt": v = int(signed(l)<signed(r))
                elif kind == "sltu": v = int(l<r)
                else: return None
                values.add(("constant", v))
            elif kind in ("add", "add32") and rk == "constant" and lk in ("arg0", "stack"):
                values.add((lk,l+signed(r)))
            elif kind in ("add", "add32") and lk == "constant" and l == 0:
                values.add((rk,r))
            elif kind == "or" and rk == "constant" and r == 0:
                values.add((lk,l))
            elif kind == "or" and lk == "constant" and l == 0:
                values.add((rk,r))
            else: return None
    return frozenset(values) if len(values)<=64 else None


def transfer(ins, before, reads):
    state = list(before)
    op, rs, rt, rd, fn = ins.op,ins.rs,ins.rt,ins.rd,ins.fn
    if not ins.word: return tuple(state)
    if op in (9,8,24,25): state[rt] = operation(state[rs],const(ins.simm),"add32" if op in (8,9) else "add")
    elif op == 15: state[rt] = const(word(ins.imm<<16))
    elif op in (12,13,14): state[rt] = operation(state[rs],const(ins.imm),{12:"and",13:"or",14:"xor"}[op])
    elif op in (10,11): state[rt] = operation(state[rs],const(ins.simm),"slt" if op==10 else "sltu")
    elif op == 0:
        kinds={32:"add32",33:"add32",34:"sub32",35:"sub32",36:"and",37:"or",38:"xor",
               42:"slt",43:"sltu",44:"add",45:"add",46:"sub",47:"sub"}
        if fn in kinds: state[rd] = operation(state[rs],state[rt],kinds[fn])
        elif fn in (0,2,3,56,58,59,60,62,63):
            n=integer(state[rt]);shift=ins.sa+(32 if fn>=60 else 0)
            if n is None: state[rd]=None
            elif fn in (0,56,60): state[rd]=const(word(n<<shift) if fn==0 else n<<shift)
            elif fn in (2,58,62): state[rd]=const(word((n&0xffffffff)>>shift) if fn==2 else n>>shift)
            else: state[rd]=const(word(signed(word(n))>>shift) if fn==3 else signed(n)>>shift)
        elif fn in (10,11): state[rd]=join(state[rd],state[rs])
        elif fn not in (8,9,17,19): state[rd]=None
    elif op in (30,32,33,34,35,36,37,38,39,55):
        address=operation(state[rs],const(ins.simm),"add")
        if address and all(kind=="arg0" for kind,_ in address) and op in (32,33,35,36,37,39):
            width={32:"s8",33:"s16",35:"s32",36:"u8",37:"u16",39:"u32"}[op]
            for _,offset in address: reads.add((ins.pc,offset,width))
            state[rt]=frozenset((f"arg0.{width}",offset) for _,offset in address)
        else: state[rt]=None
    elif op == 17 and rs in (0,2): state[rt]=None
    elif op == 18 and rs in (0,1,2): state[rt]=None
    elif op == 28: state[rd]=None
    elif op in (16,19):
        # Unmodeled coprocessor/system operations can alter general state.
        state=[const(0)]+[None]*31
    elif op not in (1,2,3,4,5,6,7,17,18,20,21,22,23,31,40,41,42,43,44,45,46,49,54,57,62,63):
        state=[const(0)]+[None]*31
    state[0]=const(0)
    return tuple(state)


def guarded_jump_table(image, pc, entry):
    """Recognize the bounded compiler switch idiom; unguarded tables stay unknown."""
    load, add = image.instruction(pc-4), image.instruction(pc-8)
    jump = image.instruction(pc)
    if not (load.op==35 and load.rt==jump.rs and load.simm==0 and add.op==0
            and add.fn in (33,45) and add.rd==load.rs):return None
    for shift_pc in range(pc-12,max(entry-4,pc-28),-4):
        shift=image.instruction(shift_pc)
        if not (shift.op==0 and shift.fn==0 and shift.sa==2 and shift.rd in (add.rs,add.rt)):continue
        base_reg=add.rt if shift.rd==add.rs else add.rs
        for guard_pc in range(shift_pc-4,max(entry-4,pc-80),-4):
            guard=image.instruction(guard_pc)
            if not (guard.op==11 and guard.rs==shift.rt and 0<guard.simm<=512):continue
            for branch_pc in (guard_pc+4,guard_pc+8):
                branch=image.instruction(branch_pc)
                if not (branch.op==4 and branch.rs==guard.rt and branch.rt==0 and branch.pc<shift_pc):continue
                between=[image.instruction(a) for a in range(branch_pc+4,pc,4)]
                if any(i.conditional or i.op in (2,3) or i.indirect for i in between):continue
                # The guarded index must not change before its multiplication by four.
                if any(shift.rt in gpr_writes(image.instruction(a))
                       for a in range(guard_pc+4,shift_pc,4)):continue
                if any(shift.rd in gpr_writes(image.instruction(a))
                       for a in range(shift_pc+4,pc-8,4)):continue
                # Recover the literal base using only this straight-line suffix.
                state=[None]*32;state[0]=const(0)
                for at in range(guard_pc,pc-8,4):state=transfer(image.instruction(at),tuple(state),set())
                base=integer(state[base_reg])
                if base is None:continue
                try:raw=image.read(base,guard.simm*4)
                except ValueError:continue
                targets=list(struct.unpack('<%dI'%guard.simm,raw))
                if not all(t%4==0 and image.contains(t) for t in targets):continue
                return {'jump_pc':hex(pc),'guard_pc':hex(guard_pc),'guard_branch_pc':hex(branch_pc),
                        'index_register':REGS[shift.rt],'table':hex(base),'count':guard.simm,
                        'default':hex(branch.target),'targets':[hex(t) for t in targets],
                        'table_sha256':sha(raw),'status':'bounded_compiler_switch'}
    return None


def gpr_writes(ins):
    if ins.op==0:
        return set() if ins.fn in (8,17,19,26,27) else {ins.rd}
    if ins.op in (8,9,10,11,12,13,14,15,24,25,30,32,33,34,35,36,37,38,39,55):return {ins.rt}
    if ins.op in (17,18) and ins.rs in (0,1,2):return {ins.rt}
    if ins.op==28:return {ins.rd}
    if ins.op==3:return {31}
    return set()


def analyze_function(image, entry, max_nodes=18000, returns=None):
    end=image.bound(entry)
    initial=[None]*32
    initial[0]=const(0);initial[4]=pointer("arg0");initial[28]=const(GP);initial[29]=pointer("stack")
    states={entry:tuple(initial)};queue=deque([entry]);reads=set();nodes={};calls={};unresolved=set();edges=set();tables={};exits={}

    def push(at, state):
        if not entry<=at<end:
            unresolved.add((at,"edge_outside_prologue_bound"));return
        edges.add((current,at))
        old=states.get(at)
        new=state if old is None else tuple(join(a,b) for a,b in zip(old,state))
        if old!=new:
            states[at]=new;queue.append(at)

    while queue:
        current=queue.popleft()
        if len(states)>max_nodes: raise ValueError(f"função excede limite de análise: {entry:#x}")
        ins=image.instruction(current);before=states[current];nodes[current]=ins
        after=transfer(ins,before,reads)
        if ins.conditional or ins.op in (2,3) or ins.indirect:
            delay=image.instruction(current+4);nodes[current+4]=delay
            delayed=transfer(delay,after,reads)
            if ins.call:
                target=ins.target if ins.op==3 else integer(before[ins.rs])
                previous=calls.get(current)
                arguments=[delayed[i] for i in range(4,8)]
                if previous: arguments=[join(a,b) for a,b in zip(previous[1],arguments)]
                calls[current]=(target,arguments)
                clobbered=list(delayed)
                for reg in [1,2,3,*range(4,16),24,25,31]:clobbered[reg]=None
                if returns:clobbered[2]=returns.get(target)
                push(current+8,tuple(clobbered))
            elif ins.indirect:
                if ins.rs!=31:
                    table=guarded_jump_table(image,current,entry)
                    if table:
                        tables[current]=table
                        for target in set(table['targets']):push(int(target,16),delayed)
                    else:unresolved.add((current,"indirect_jump_not_resolved"))
                else:exits[current]=delayed[2]
            elif ins.op==2:push(ins.target,delayed)
            else:
                # A constant branch can be decided; otherwise both paths are possible.
                l,r=integer(before[ins.rs]),integer(before[ins.rt]);decision=None
                if ins.op in (4,5,20,21) and l is not None and r is not None:
                    decision=(l==r)==(ins.op in (4,20))
                if decision is not False:push(ins.target,delayed)
                if decision is not True:push(current+8,after if ins.likely else delayed)
        else:push(current+4,after)
    descriptions=[]
    for pc,(target,args) in sorted(calls.items()):
        kinds=args[1]
        literals=sorted(n for kind,n in (kinds or ()) if kind=="constant")
        descriptions.append({"pc":hex(pc),"callee":hex(target) if target is not None else None,
                             "role":SINKS.get(target,"untranslated_call"),"arguments":[describe(v) for v in args],
                             "literal_clip_ids":literals if target in SINKS else [],
                             "clip_argument_fully_constant":bool(kinds) and all(k=="constant" for k,_ in kinds)})
    return_value=None
    if exits and not unresolved:
        for value in exits.values():
            if value is None:return_value=None;break
            return_value=value if return_value is None else join(return_value,value)
            if return_value is None:break
    return {"entry":hex(entry),"prologue_bound":hex(end),"instructions":len(nodes),
            "instruction_bytes_sha256":sha(b"".join(struct.pack("<I",nodes[pc].word) for pc in sorted(nodes))),
            "calls":descriptions,"argument0_field_reads":[{"pc":hex(pc),"offset":hex(offset),"type":width} for pc,offset,width in sorted(reads)],
            "return_summary":describe(return_value),"return_abstract_value":return_value,
            "unresolved_edges":[{"pc":hex(pc),"reason":reason} for pc,reason in sorted(unresolved)],
            "jump_tables":[tables[pc] for pc in sorted(tables)],
            "edges":[[hex(a),hex(b)] for a,b in sorted(edges)],
            "listing":[[hex(pc),f"{nodes[pc].word:08x}",nodes[pc].text()] for pc in sorted(nodes)]}


def recover(image, depth=2):
    routes=dispatchers(image)
    roots={int(c["handler"],16) for c in routes["actions"]["cases"] if c["handler"]}
    roots|={0x0184f5c0,0x01853d30,0x01859920,0x01876b50,0x017bb0a0}
    pending=deque((r,0) for r in sorted(roots));functions={};levels={}
    while pending:
        entry,level=pending.popleft()
        if entry in functions or not image.contains(entry):continue
        function=analyze_function(image,entry)
        functions[entry]=function;levels[entry]=level
        if level<depth:
            for call in function["calls"]:
                target=int(call["callee"],16) if call["callee"] else None
                if target is not None and target not in SINKS and image.contains(target):pending.append((target,level+1))
    # Propagate finite return alternatives; no callee is replaced by a success stub.
    for _ in range(2):
        returns={e:f['return_abstract_value'] for e,f in functions.items()}
        functions={e:analyze_function(image,e,returns=returns) for e in sorted(functions)}
    associations={clip:[] for clip in range(1105)};ambiguous=[]
    for entry,function in sorted(functions.items()):
        for call in function["calls"]:
            if call["role"] not in SINKS.values():continue
            if not call["clip_argument_fully_constant"]:ambiguous.append(dict(call,function=hex(entry)))
            for clip in call["literal_clip_ids"]:
                if clip<1105:associations[clip].append({"function":hex(entry),"call_pc":call["pc"],
                    "role":call["role"],"arguments":call["arguments"],"constant_alternatives":call["literal_clip_ids"],
                    "status":"static_call_argument","runtime_enabled":False})
    action_reach={}
    for case in routes["actions"]["cases"]:
        if not case["handler"]:continue
        pending=[int(case["handler"],16)];seen=set()
        while pending:
            at=pending.pop()
            if at in seen or at not in functions:continue
            seen.add(at)
            pending.extend(int(c["callee"],16) for c in functions[at]["calls"] if c["callee"])
        action_reach[case["value"]]=seen
    clips=[]
    for clip,refs in associations.items():
        actions=sorted(action for action,seen in action_reach.items()
                       if any(int(ref["function"],16) in seen for ref in refs))
        clips.append({"clip":clip,"action_contexts":actions,"references":refs,
                      "classification":"code_reference" if refs else "not_resolved_in_analyzed_functions",
                      "semantic_name":None,"runtime_enabled":False})
    for function in functions.values():function.pop('return_abstract_value')
    document={"schema_version":1,"sources":image.sources,"routing":routes,"analysis_depth":depth,
            "functions":[functions[e] for e in sorted(functions)],"clips":clips,"unresolved_animation_calls":ambiguous,
            "summary":{"action_cases":len(routes["actions"]["cases"]),"request_cases":23,
                       "action1_substate_cases":len(routes["action1_substates"]["cases"]),
                       "functions_analyzed":len(functions),"clips_with_code_references":sum(bool(c["references"]) for c in clips),
                       "animation_call_sites":sum(c["role"] in SINKS.values() for f in functions.values() for c in f["calls"]),
                       "unresolved_animation_calls":len(ambiguous),"unresolved_control_edges":sum(len(f["unresolved_edges"]) for f in functions.values()),
                       "guarded_jump_tables":sum(len(f['jump_tables']) for f in functions.values()),
                       "finite_return_propagation_passes":2},
            "scope":"Exact recovered routing; conservative static call arguments and call-graph contexts. No full actions, inferred semantic names, feasibility proof, dynamic table recovery or gameplay integration."}
    return enrich_contexts(document)


def enrich_contexts(document):
    """Link action-1 block reachability and retain original branch instructions."""
    functions={f['entry']:f for f in document['functions']}
    action1=functions['0x1876b50']
    edges={}
    for a,b in action1['edges']:edges.setdefault(a,set()).add(b)
    contexts={}
    for case in document['routing']['action1_substates']['cases']:
        pending=[case['block']];seen=set()
        while pending:
            pc=pending.pop()
            if pc in seen:continue
            seen.add(pc);pending.extend(edges.get(pc,()))
        targets=[c['callee'] for c in action1['calls'] if c['pc'] in seen and c['callee']]
        callees=set()
        while targets:
            function=targets.pop()
            if function in callees or function not in functions:continue
            callees.add(function)
            targets.extend(c['callee'] for c in functions[function]['calls'] if c['callee'])
        contexts[case['value']]=(seen,callees)
    for clip in document['clips']:
        clip['action1_substate_contexts']=sorted(value for value,(nodes,callees) in contexts.items()
            if any((ref['function']=='0x1876b50' and ref['call_pc'] in nodes)
                   or ref['function'] in callees for ref in clip['references']))
    for function in document['functions']:
        function['branch_conditions']=[{'pc':pc,'word':word,'condition_instruction':text,
            'taken_block':hex(Instruction(int(pc,16),int(word,16)).target),
            'fallthrough':hex(int(pc,16)+8),
            'delay_slot_executes_on_fallthrough':not Instruction(int(pc,16),int(word,16)).likely}
            for pc,word,text in function['listing'] if Instruction(int(pc,16),int(word,16)).conditional]
    document['summary']['late_bound_field_animation_calls']=sum(
        any(a.startswith('arg0.') for a in c['arguments'][1]) for c in document['unresolved_animation_calls'])
    document['summary']['fully_unknown_animation_calls']=sum(
        c['arguments'][1]==['unresolved'] for c in document['unresolved_animation_calls'])
    document['analysis_assumptions']={
        'function_bounds':'next stack-allocation prologue; shared/external edges remain unresolved',
        'argument0_fields':'offsets relative to parameter 0, not universally player or anatomical names',
        'contexts':'possible structural call/branch reachability; feasibility and runtime timing not established',
        'constant_arguments':'finite abstract alternatives; register clobbers and delay slots preserved',
        'rewritten_dispatchers':'return block identifiers; never call PS2 addresses as Windows pointers'}
    return document


def generate_js(document):
    data=json.dumps(document["routing"],separators=(",",":"))
    return ('/* Generated from verified SLES/OVER routing; not complete action execution. */\n'
            '(function(root){"use strict";const routing='+data+';\n'
            'function checked(value,max){if(!Number.isInteger(value)||value<0||value>max)throw new Error("Estado fora do domínio");}\n'
            'function lookup(part,value){const found=part.cases.find(c=>c.value===value);return found?found.block:part.default;}\n'
            'const api={routing,request:value=>{checked(value,0xffffffff);value&=255;return routing.requests.targets[value]||routing.requests.default;},\n'
            'action:value=>{checked(value,255);return lookup(routing.actions,value);},\n'
            'action1Substate:value=>{checked(value,65535);return lookup(routing.action1_substates,value);}};\n'
            'if(typeof module!=="undefined"&&module.exports)module.exports=api;else root.Pes3Actions=api;})(globalThis);\n')


def generate_cpp(document):
    routes=document["routing"]
    lines=['// Generated exact routing only; no complete action/pose/physics update.',
           '#pragma once','#include <cstdint>','namespace pes3_recovered {',
           'inline std::uint32_t request_block(std::uint32_t event) {',
           '  static constexpr std::uint32_t table[] = {'+','.join(v+'u' for v in routes['requests']['targets'])+'};',
           '  event &= 255u; return event < 23 ? table[event] : '+routes['requests']['default']+'u;','}']
    for name,key,ctype in [('action_block','actions','std::uint8_t'),('action1_substate_block','action1_substates','std::uint16_t')]:
        lines += [f'inline std::uint32_t {name}({ctype} value) {{','  switch (value) {']
        lines += [f'    case {c["value"]}: return {c["block"]}u;' for c in routes[key]['cases']]
        lines += ['    default: return '+routes[key]['default']+'u;','  }','}']
    return '\n'.join(lines+['} // namespace pes3_recovered',''])


def main():
    parser=argparse.ArgumentParser(description="Recuperar os roteamentos e referências de animação PES 3")
    parser.add_argument('--elf',type=Path,required=True);parser.add_argument('--over',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--depth',type=int,default=2,choices=range(4))
    args=parser.parse_args()
    if args.output.exists():parser.error('escolha uma pasta de saída nova')
    image=Image(args.elf,args.over);result=recover(image,args.depth)
    args.output.mkdir(parents=True)
    (args.output/'actions.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.output/'action_dispatch.js').write_text(generate_js(result))
    (args.output/'action_dispatch.hpp').write_text(generate_cpp(result))
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()
