// Generated exact routing only; no complete action/pose/physics update.
#pragma once
#include <cstdint>
namespace pes3_recovered {
inline std::uint32_t request_block(std::uint32_t event) {
  static constexpr std::uint32_t table[] = {0x184f600u,0x184fcb4u,0x184fb4cu,0x18506d0u,0x185081cu,0x1851f20u,0x18522ecu,0x18517a8u,0x18509a8u,0x1853d08u,0x1852b40u,0x1851274u,0x1850b84u,0x185116cu,0x1853d08u,0x1850528u,0x184ffd8u,0x1852f1cu,0x185375cu,0x1853d08u,0x1850ec8u,0x1853b30u,0x1853c9cu};
  event &= 255u; return event < 23 ? table[event] : 0x01853d08u;
}
inline std::uint32_t action_block(std::uint8_t value) {
  switch (value) {
    case 255: return 0x1880e4cu;
    case 253: return 0x1880e3cu;
    case 40: return 0x1880e2cu;
    case 39: return 0x1880e1cu;
    case 37: return 0x1880e0cu;
    case 69: return 0x1880dfcu;
    case 65: return 0x1880decu;
    case 10: return 0x1880decu;
    case 29: return 0x1880ddcu;
    case 27: return 0x1880dccu;
    case 26: return 0x1880dbcu;
    case 23: return 0x1880dacu;
    case 38: return 0x1880d9cu;
    case 42: return 0x1880d8cu;
    case 24: return 0x1880d7cu;
    case 22: return 0x1880d6cu;
    case 64: return 0x1880d5cu;
    case 54: return 0x1880d4cu;
    case 53: return 0x1880d3cu;
    case 21: return 0x1880d2cu;
    case 67: return 0x1880d1cu;
    case 15: return 0x1880d1cu;
    case 20: return 0x1880d0cu;
    case 66: return 0x1880cfcu;
    case 41: return 0x1880cecu;
    case 36: return 0x1880cdcu;
    case 18: return 0x1880cccu;
    case 17: return 0x1880cbcu;
    case 16: return 0x1880cacu;
    case 49: return 0x1880c9cu;
    case 48: return 0x1880c8cu;
    case 71: return 0x1880c7cu;
    case 70: return 0x1880c6cu;
    case 51: return 0x1880c5cu;
    case 72: return 0x1880c4cu;
    case 50: return 0x1880c3cu;
    case 46: return 0x1880c2cu;
    case 47: return 0x1880c1cu;
    case 43: return 0x1880c0cu;
    case 14: return 0x1880bfcu;
    case 12: return 0x1880becu;
    case 45: return 0x1880bdcu;
    case 44: return 0x1880bccu;
    case 33: return 0x1880bbcu;
    case 31: return 0x1880bacu;
    case 30: return 0x1880b9cu;
    case 32: return 0x1880b8cu;
    case 34: return 0x1880b7cu;
    case 55: return 0x1880b6cu;
    case 68: return 0x1880b68u;
    case 13: return 0x1880b68u;
    case 11: return 0x1880b58u;
    case 9: return 0x1880b48u;
    case 8: return 0x1880b38u;
    case 6: return 0x1880b28u;
    case 5: return 0x1880b28u;
    case 3: return 0x1880b18u;
    case 2: return 0x1880b08u;
    case 4: return 0x1880af8u;
    case 1: return 0x1880ae8u;
    case 7: return 0x1880ad8u;
    case 0: return 0x1880ac8u;
    default: return 0x01880e5cu;
  }
}
inline std::uint32_t action1_substate_block(std::uint16_t value) {
  switch (value) {
    case 48: return 0x187ac48u;
    case 33: return 0x187a69cu;
    case 32: return 0x187a610u;
    case 24: return 0x187a49cu;
    case 20: return 0x187a0fcu;
    case 16: return 0x1878368u;
    case 19: return 0x187830cu;
    case 18: return 0x1878300u;
    case 56: return 0x1877c60u;
    case 55: return 0x1877c44u;
    case 72: return 0x18775acu;
    case 64: return 0x18775a8u;
    case 1: return 0x1876cf4u;
    default: return 0x01876c20u;
  }
}
} // namespace pes3_recovered
