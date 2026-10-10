// Execution support for statically translated, reached PES instruction paths.
// Selected host binary32/FPU/VU model; no PS2 devices, timing or full emulator.
#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>

namespace pes3_lift {
inline std::int64_t s32(std::uint64_t v) {
  const auto n = static_cast<std::uint32_t>(v);
  return n < 0x80000000u ? n : static_cast<std::int64_t>(n) - 0x100000000ll;
}
inline std::int64_t s64(std::uint64_t v) {
  return v < 0x8000000000000000ull ? static_cast<std::int64_t>(v)
                                : -static_cast<std::int64_t>(~v) - 1;
}
inline std::uint64_t w32(std::uint64_t v) { return static_cast<std::uint64_t>(s32(v)); }
inline std::uint32_t bits(float v) { std::uint32_t out; std::memcpy(&out, &v, 4); return out; }
inline float value(std::uint32_t v) { float out; std::memcpy(&out, &v, 4); return out; }
inline float rounded(double v) {
  const auto out = static_cast<float>(v);
  if (!std::isfinite(out)) throw std::runtime_error("non-finite float outside model");
  return out;
}
inline float vector_value(double v) {
  const auto out = rounded(v); const auto raw = bits(out);
  return (raw & 0x7f800000u) == 0 ? value(raw & 0x80000000u) : out;
}
inline std::uint64_t asr(std::uint64_t n, unsigned shift) {
  if (!shift) return n;
  return (n >> shift) | ((n >> 63) ? (~std::uint64_t{0} << (64 - shift)) : 0);
}

struct Cpu {
  std::uint8_t* ram; std::uint8_t* scratch;
  std::array<std::uint64_t,32> r{}, upper{};
  std::array<std::uint32_t,32> f{};
  std::array<std::array<float,4>,32> vf{};
  std::array<float,4> acc{};
  float scalar_acc = 0, q = 0;
  bool condition = false, annul = false, pending_set = false;
  std::uint32_t pc = 0, word = 0, pending = 0;
  std::uint64_t lo = 0, hi = 0, instructions = 0;
  std::uint64_t trace_hash = 14695981039346656037ull;

  Cpu(std::uint8_t* main, std::uint8_t* local) : ram(main), scratch(local) { vf[0][3] = 1; }
  std::uint8_t* address(std::uint32_t at, std::size_t count) {
    if (at <= 0x02000000u && count <= 0x02000000u - at) return ram + at;
    if (at >= 0x70000000u && at <= 0x70004000u && count <= 0x70004000u - at)
      return scratch + (at - 0x70000000u);
    throw std::runtime_error("memory outside RAM/scratch model");
  }
  template<class T> T read(std::uint32_t at) {
    T out; std::memcpy(&out, address(at, sizeof(T)), sizeof(T)); return out;
  }
  template<class T> void write(std::uint32_t at, T v) {
    std::memcpy(address(at, sizeof(T)), &v, sizeof(T));
  }
  void branch(std::uint32_t target) { pending = target; pending_set = true; }
  void mark(std::uint32_t original) {
    word = original;
    if (read<std::uint32_t>(pc) != original) throw std::runtime_error("translated instruction changed");
    for (unsigned shift = 0; shift < 32; shift += 8) {
      trace_hash ^= (pc >> shift) & 255; trace_hash *= 1099511628211ull;
    }
    for (unsigned shift = 0; shift < 32; shift += 8) {
      trace_hash ^= (word >> shift) & 255; trace_hash *= 1099511628211ull;
    }
  }
  void mult(unsigned rd, std::uint64_t left, std::uint64_t right, bool signed_op) {
    const auto product = signed_op ? static_cast<std::uint64_t>(s32(left) * s32(right))
                                  : static_cast<std::uint64_t>(static_cast<std::uint32_t>(left)) * static_cast<std::uint32_t>(right);
    lo = w32(product); hi = w32(product >> 32); if (rd) r[rd] = lo;
  }
  void divide(std::uint64_t left, std::uint64_t right, bool signed_op) {
    if (signed_op) {
      const auto a = s32(left), b = s32(right);
      if (!b) { lo = a >= 0 ? ~std::uint64_t{0} : 1; hi = static_cast<std::uint64_t>(a); }
      else if (a == -2147483648ll && b == -1) { lo = static_cast<std::uint64_t>(a); hi = 0; }
      else { lo = static_cast<std::uint64_t>(a / b); hi = static_cast<std::uint64_t>(a % b); }
    } else {
      const auto a = static_cast<std::uint32_t>(left), b = static_cast<std::uint32_t>(right);
      lo = w32(b ? a / b : 0xffffffffu); hi = w32(b ? a % b : a);
    }
  }
  void load_quad(unsigned rt, std::uint32_t at) {
    r[rt] = read<std::uint64_t>(at); upper[rt] = read<std::uint64_t>(at + 8);
  }
  void store_quad(unsigned rt, std::uint32_t at) {
    write(at, r[rt]); write(at + 8, upper[rt]);
  }
  void load_vector(unsigned rt, std::uint32_t at) {
    for (unsigned i = 0; i < 4; ++i) vf[rt][i] = rounded(read<float>(at + i * 4));
  }
  void store_vector(unsigned rt, std::uint32_t at) {
    for (unsigned i = 0; i < 4; ++i) write(at + i * 4, vf[rt][i]);
  }
  void cop1(std::uint32_t w) {
    const unsigned rs = (w >> 21) & 31, rt = (w >> 16) & 31,
      fs = (w >> 11) & 31, fd = (w >> 6) & 31, fn = w & 63;
    if (rs == 4) { f[fs] = static_cast<std::uint32_t>(r[rt]); return; }
    if (rs == 0) { r[rt] = w32(f[fs]); return; }
    if (rs == 8 && rt < 2) {
      if (condition == static_cast<bool>(rt)) branch(pc + 4 + static_cast<std::int16_t>(w) * 4);
      return;
    }
    if (rs == 20 && fn == 32) { f[fd] = bits(rounded(static_cast<double>(s32(f[fs])))); return; }
    if (rs != 16) throw std::runtime_error("unsupported COP1 format");
    const double left = value(f[fs]), right = value(f[rt]);
    if (fn <= 3 || fn == 26 || fn == 28 || fn == 50 || fn == 52 || fn == 54) {
      rounded(left); rounded(right);
      switch (fn) {
        case 0: f[fd] = bits(rounded(left + right)); return;
        case 1: f[fd] = bits(rounded(left - right)); return;
        case 2: f[fd] = bits(rounded(left * right)); return;
        case 3:
          if (!right) throw std::runtime_error("division by zero outside float model");
          f[fd] = bits(rounded(left / right)); return;
        case 26: scalar_acc = rounded(left * right); return;
        case 28: f[fd] = bits(rounded(static_cast<double>(scalar_acc) + rounded(left * right))); return;
        case 50: condition = left == right; return;
        case 52: condition = left < right; return;
        case 54: condition = left <= right; return;
      }
    }
    if (fn == 5) { f[fd] = f[fs] & 0x7fffffffu; return; }
    if (fn == 6) { f[fd] = f[fs]; return; }
    if (fn == 7) { f[fd] = f[fs] ^ 0x80000000u; return; }
    if (fn == 4 && fs == rt && left >= 0 && std::isfinite(left)) { f[fd] = bits(rounded(std::sqrt(left))); return; }
    if (fn == 36 && std::isfinite(left) && left >= -2147483648.0 && left < 2147483648.0) {
      f[fd] = static_cast<std::uint32_t>(static_cast<std::int64_t>(std::trunc(left))); return;
    }
    throw std::runtime_error("unsupported COP1 operation/domain");
  }
  void cop2(std::uint32_t w) {
    const unsigned rs = (w >> 21) & 31, ft = (w >> 16) & 31,
      fs = (w >> 11) & 31, fd = (w >> 6) & 31, fn = w & 63;
    if (rs == 5) { vf[fs] = {value(static_cast<std::uint32_t>(r[ft])),value(static_cast<std::uint32_t>(r[ft] >> 32)),0,0}; return; }
    if (rs < 16) throw std::runtime_error("unsupported COP2 transfer");
    const unsigned mask = rs & 15;
    const auto source = vf[fs], other = vf[ft], old_acc = acc;
    auto* destination = &vf[fd]; int broadcast = -1, kind = -1;
    if (fn >= 60) {
      const unsigned index = (w & 3) | ((w >> 4) & 0x7c);
      if (index == 48 || index == 49) {
        for (unsigned lane = 0; lane < 4; ++lane) if (mask & (8 >> lane))
          vf[ft][lane] = source[index == 49 ? (lane + 1) & 3 : lane];
        return;
      }
      if (index == 57) { q = vector_value(std::sqrt(std::abs(static_cast<double>(vector_value(other[(w >> 23) & 3]))))); return; }
      if (index == 59) return; // Selected VWAITQ model has no timing.
      if (index >= 24 && index <= 27) { kind = 2; broadcast = index - 24; destination = &acc; }
      else if (index >= 8 && index <= 11) { kind = 3; broadcast = index - 8; destination = &acc; }
    } else if (fn <= 3) { kind = 0; broadcast = fn; }
    else if (fn <= 7) { kind = 1; broadcast = fn - 4; }
    else if (fn <= 11) { kind = 3; broadcast = fn - 8; }
    else if (fn >= 24 && fn <= 27) { kind = 2; broadcast = fn - 24; }
    else if (fn == 32) kind = 4;
    else if (fn == 42) kind = 2;
    else if (fn == 44) kind = 1;
    if (kind < 0) throw std::runtime_error("unsupported VU operation");
    for (unsigned lane = 0; lane < 4; ++lane) {
      if (!(mask & (8 >> lane))) continue;
      const double left = vector_value(source[lane]);
      const double right = vector_value(kind == 4 ? q : other[broadcast < 0 ? lane : broadcast]);
      float out;
      if (kind == 0 || kind == 4) out = vector_value(left + right);
      else if (kind == 1) out = vector_value(left - right);
      else if (kind == 2) out = vector_value(left * right);
      else out = vector_value(static_cast<double>(vector_value(old_acc[lane])) + vector_value(left * right));
      if (destination == &acc || fd != 0) (*destination)[lane] = out;
    }
    vf[0] = {0,0,0,1};
  }
};
} // namespace pes3_lift
