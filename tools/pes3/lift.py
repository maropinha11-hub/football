#!/usr/bin/env python3
"""Statically translate reached original instruction words into guarded C++.

This preserves guest registers/addresses and a selected arithmetic model.
It is a partial static recompilation, not recovered original C++ source or
an engine-ready semantic rewrite. Untranslated instructions fail closed.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from mips import Instruction


def translate(ins):
    op, rs, rt, rd, sa, fn = ins.op, ins.rs, ins.rt, ins.rd, ins.sa, ins.fn
    r = lambda i: f"c.r[{i}]"
    a, b, d = r(rs), r(rt), r(rd)
    address = f"static_cast<std::uint32_t>({a} + ({ins.simm}ll))"
    if op == 0:
        if fn == 0: return f"{d} = w32({b} << {sa});"
        if fn == 2: return f"{d} = w32(static_cast<std::uint32_t>({b}) >> {sa});"
        if fn == 3: return f"{d} = asr(w32({b}), {sa});"
        if fn == 4: return f"{d} = w32({b} << ({a} & 31));"
        if fn == 6: return f"{d} = w32(static_cast<std::uint32_t>({b}) >> ({a} & 31));"
        if fn == 8: return f"c.branch(static_cast<std::uint32_t>({a}));"
        if fn == 9: return f"c.branch(static_cast<std::uint32_t>({a})); {d} = {ins.pc + 8}u;"
        if fn in (10, 11): return f"if ({b} {'==' if fn == 10 else '!='} 0) {d} = {a};"
        if fn in (16, 18): return f"{d} = c.{'hi' if fn == 16 else 'lo'};"
        if fn in (24, 25): return f"c.mult({rd}, {a}, {b}, {'true' if fn == 24 else 'false'});"
        if fn in (26, 27): return f"c.divide({a}, {b}, {'true' if fn == 26 else 'false'});"
        if fn in (32, 33, 34, 35): return f"{d} = w32({a} {'+' if fn < 34 else '-'} {b});"
        if fn in (36, 37, 38): return f"{d} = {a} { {36:'&',37:'|',38:'^'}[fn]} {b};"
        if fn in (42, 43): return f"{d} = {'s64('+a+')' if fn == 42 else a} < {'s64('+b+')' if fn == 42 else b};"
        if fn in (44, 45, 46, 47): return f"{d} = {a} {'+' if fn < 46 else '-'} {b};"
        if fn in (56, 60): return f"{d} = {b} << {sa + (32 if fn == 60 else 0)};"
        if fn in (58, 62): return f"{d} = {b} >> {sa + (32 if fn == 62 else 0)};"
        if fn in (59, 63): return f"{d} = asr({b}, {sa + (32 if fn == 63 else 0)});"
    elif op == 1 and rt in (0, 1):
        return f"if (s64({a}) {'<' if rt == 0 else '>='} 0) c.branch({ins.target}u);"
    elif op in (2, 3):
        return (f"c.r[31] = {ins.pc + 8}u; " if op == 3 else "") + f"c.branch({ins.target}u);"
    elif op in (4, 5, 6, 7, 20, 21):
        test = f"{a} {'==' if op in (4, 20) else '!='} {b}" if op in (4, 5, 20, 21) else f"s64({a}) {'<=' if op == 6 else '>'} 0"
        return f"if ({test}) c.branch({ins.target}u);" + (" else c.annul = true;" if op in (20,21) else "")
    elif op in (8, 9): return f"{b} = w32({a} + ({ins.simm}ll));"
    elif op == 10: return f"{b} = s64({a}) < {ins.simm}ll;"
    elif op == 11: return f"{b} = {a} < static_cast<std::uint64_t>({ins.simm}ll);"
    elif op in (12, 13, 14): return f"{b} = {a} { {12:'&',13:'|',14:'^'}[op]} {ins.imm}u;"
    elif op == 15: return f"{b} = {int(ins.imm << 16) if ins.imm < 32768 else int(ins.imm << 16) + (1 << 64) - (1 << 32)}ull;"
    elif op in (24, 25): return f"{b} = {a} + ({ins.simm}ll);"
    elif op in (32, 33, 35, 36, 37, 39, 55):
        kind = {32:'std::int8_t',33:'std::int16_t',35:'std::int32_t',36:'std::uint8_t',37:'std::uint16_t',39:'std::uint32_t',55:'std::uint64_t'}[op]
        return f"{b} = static_cast<std::uint64_t>(c.read<{kind}>({address}));"
    elif op == 30: return f"c.load_quad({rt}, {address});"
    elif op == 28 and fn in (24, 25):
        product = f"s32({a}) * s32({b})" if fn == 24 else f"static_cast<std::uint64_t>(static_cast<std::uint32_t>({a})) * static_cast<std::uint32_t>({b})"
        return f"{d} = w32({product});" if rd else ""
    elif op == 17: return f"c.cop1({ins.word}u);"
    elif op == 18: return f"c.cop2({ins.word}u);"
    elif op == 49: return f"c.f[{rt}] = c.read<std::uint32_t>({address});"
    elif op == 57: return f"c.write({address}, c.f[{rt}]);"
    elif op == 54: return f"c.load_vector({rt}, {address});"
    elif op == 62: return f"c.store_vector({rt}, {address});"
    elif op in (40, 41, 43, 63):
        kind = {40:'std::uint8_t',41:'std::uint16_t',43:'std::uint32_t',63:'std::uint64_t'}[op]
        return f"c.write({address}, static_cast<{kind}>({b}));"
    elif op == 31: return f"c.store_quad({rt}, {address});"
    return 'throw std::runtime_error("unsupported translated instruction");'


ABI = '''#pragma once
#include <cstdint>
// Caller supplies mutable copies of 32 MiB EE RAM and 16 KiB scratchpad.
// Output status 0 means a modeled function call returned; no full-frame claim.
struct Pes3LiftResult {
  std::uint32_t status, pc, word, reserved;
  std::uint64_t instructions, trace_hash;
  std::uint64_t registers[32];
  std::uint32_t float_registers[32];
  char error[192];
};
extern "C" int pes3_run_lifted(std::uint8_t* ram, std::uint8_t* scratch,
  std::uint32_t entry, const std::uint64_t* args, std::uint32_t count,
  std::uint32_t budget, Pes3LiftResult* result);
// Optional 32 raw binary32 FPU input registers for selected pose calls.
extern "C" int pes3_run_lifted_f32(std::uint8_t* ram, std::uint8_t* scratch,
  std::uint32_t entry, const std::uint64_t* args, std::uint32_t count,
  const std::uint32_t* float_registers, std::uint32_t budget, Pes3LiftResult* result);
'''


def generate(words, output):
    pages = defaultdict(list)
    for pc, word in sorted(words.items()):
        if pc & 3 or not 0 <= word <= 0xffffffff:
            raise ValueError("palavra/endereço de instrução inválido")
        pages[pc >> 12].append(Instruction(pc, word))
    lines = ['// Generated static recompilation of reached original paths only.',
             '#include "lift_runtime.hpp"', '#include "lift_api.hpp"', 'using namespace pes3_lift;']
    for page, instructions in pages.items():
        lines += [f'static void page_{page:x}(Cpu& c) {{', '  switch(c.pc) {']
        for ins in instructions:
            lines += [f'    case {ins.pc}u: c.mark({ins.word}u); {translate(ins)} break;']
        lines += ['    default: throw std::runtime_error("untranslated path");', '  }', '}']
    lines += ['static void step(Cpu& c) {', '  switch(c.pc >> 12) {']
    lines += [f'    case {page}u: page_{page:x}(c); return;' for page in pages]
    lines += ['    default: throw std::runtime_error("untranslated code page");', '  }', '}',
      'extern "C" int pes3_run_lifted_f32(std::uint8_t* ram, std::uint8_t* scratch,',
      '  std::uint32_t entry, const std::uint64_t* args, std::uint32_t count,',
      '  const std::uint32_t* float_registers, std::uint32_t budget, Pes3LiftResult* result) {',
      '  if(!result) return -1;', '  *result = {};',
      '  if(!ram || !scratch || count > 8 || (count && !args) || !budget) { result->status=1; return 1; }',
      '  Cpu c(ram,scratch); c.pc=entry; c.r[28]=0x012adef0u; c.r[29]=0x01ffc000u; c.r[31]=0xfffffffcu;',
      '  for(unsigned i=0;i<count;++i) c.r[4+i]=args[i];', '  try {',
      '    if(float_registers) std::memcpy(c.f.data(),float_registers,sizeof(c.f));',
      '    const std::uint32_t little = 1;',
      '    if(*reinterpret_cast<const std::uint8_t*>(&little)!=1) throw std::runtime_error("host must be little endian");',
      '    while(c.pc != 0xfffffffcu) {',
      '      if(c.instructions >= budget) throw std::runtime_error("instruction budget exceeded");',
      '      const auto next=c.pending; const bool has_next=c.pending_set;',
      '      c.pending_set=false; c.annul=false;', '      step(c); ++c.instructions; c.r[0]=0;',
      '      c.pc=has_next ? next : c.pc+(c.annul ? 8 : 4);', '    }',
      '  } catch(const std::exception& error) {',
      '    result->status=1; std::strncpy(result->error,error.what(),sizeof(result->error)-1);',
      '  }',
      '  result->pc=c.pc; result->word=c.word; result->instructions=c.instructions; result->trace_hash=c.trace_hash;',
      '  std::memcpy(result->registers,c.r.data(),sizeof(result->registers));',
      '  std::memcpy(result->float_registers,c.f.data(),sizeof(result->float_registers));',
      '  return static_cast<int>(result->status);', '}',
      'extern "C" int pes3_run_lifted(std::uint8_t* ram, std::uint8_t* scratch,',
      '  std::uint32_t entry, const std::uint64_t* args, std::uint32_t count,',
      '  std::uint32_t budget, Pes3LiftResult* result) {',
      '  return pes3_run_lifted_f32(ram,scratch,entry,args,count,nullptr,budget,result);', '}', '']
    output.mkdir(parents=True, exist_ok=False)
    (output / 'lifted_program.cpp').write_text('\n'.join(lines))
    (output / 'lift_api.hpp').write_text(ABI)
    (output / 'lift_runtime.hpp').write_bytes(Path(__file__).with_name('lift_runtime.hpp').read_bytes())
    return {'instructions_translated': len(words), 'pages': len(pages),
            'scope': 'Reached instruction paths; guest register/memory representation, selected host arithmetic, no devices or complete PS2 frame.'}


def main():
    parser = argparse.ArgumentParser(description='Recompilar caminhos registrados do PES em C++')
    parser.add_argument('--words', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = generate({int(k,16):v for k,v in json.loads(args.words.read_text()).items()}, args.output)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
