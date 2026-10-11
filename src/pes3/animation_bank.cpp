#include "animation_bank.hpp"
#include "pes_skeleton_bind_bits.h"
#include <algorithm>
#include <cstring>
#include <fstream>
#include <limits>

namespace {
unsigned word(const unsigned char* p) {
  return unsigned(p[0]) | unsigned(p[1]) << 8 | unsigned(p[2]) << 16 | unsigned(p[3]) << 24;
}
float number(unsigned raw) { float out; std::memcpy(&out, &raw, 4); return out; }
unsigned crc32(const std::vector<unsigned char>& data) {
  unsigned crc = ~0u;
  for (auto byte : data) {
    crc ^= byte;
    for (unsigned i = 0; i < 8; ++i) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}
bool fail(std::string& error, const char* message) { error = message; return false; }
}
namespace pes3 {
bool AnimationBank::inspect(const std::vector<unsigned char>& data, std::vector<Clip>& out,
                            std::string& error) {
  error.clear();
  if (data.size() < 32 || data.size() > 32*1024*1024 || std::memcmp(data.data(), "FPSANM14", 8))
    return fail(error, "Assinatura/tamanho FPSANM14 invalido");
  const auto* p = data.data();
  const unsigned count = word(p+8);
  if (!count || count > 1105 || word(p+12) != 32 || word(p+16) != 14 ||
      word(p+20) != 19 || word(p+24) != 164 || word(p+28) || 32+count*16 > data.size())
    return fail(error, "Cabecalho FPSANM14 invalido");
  std::vector<Clip> candidate;
  unsigned next = 32+count*16;
  for (unsigned i = 0; i < count; ++i) {
    const auto* entry = p+32+i*16;
    const unsigned offset = word(entry+8), length = word(entry+12);
    if (word(entry) != i || offset != next || length < 32 || offset > data.size() || length > data.size()-offset)
      return fail(error, "Diretorio/intervalo FPSANM14 invalido");
    const auto* block = p+offset;
    const unsigned table = word(block+16);
    const float duration = number(word(block+8));
    if (word(block) != 0x20011119u || word(block+4) != 0x20000002u ||
        word(block+8) != word(entry+4) || word(block+12) != 60 ||
        !std::isfinite(duration) || !(duration > 0 && duration <= 4096) || table > length-4)
      return fail(error, "Bloco de movimento invalido");
    const unsigned keys = word(block+table);
    if (!keys || keys > 512 || table != 28+164*keys || length != 32+172*keys)
      return fail(error, "Tabela de chaves invalida");
    float previous = 0;
    for (unsigned key = 0; key < keys; ++key) {
      const float endpoint = number(word(block+table+4+key*8));
      if (word(block+table+8+key*8) != 28+164*key ||
          (key == keys-1 ? endpoint != 0 : !std::isfinite(endpoint) || !(endpoint > previous && endpoint <= duration)))
        return fail(error, "Tempo/offset de chave invalido");
      for (unsigned axis = 0; axis < 3; ++axis)
        if (!std::isfinite(number(word(block+28+164*key+8+axis*4))))
          return fail(error, "Translacao nao finita");
      previous = endpoint;
    }
    candidate.push_back(Clip{offset, length, duration});
    next += length;
  }
  if (next != data.size()) return fail(error, "Bytes excedentes no FPSANM14");
  out.swap(candidate);
  return true;
}
bool AnimationBank::load(const std::string& path, std::string& error) {
  bytes.clear(); clips.clear(); error.clear();
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file) return fail(error, "Instale o arquivo com importar-pes3.bat");
  const auto size = file.tellg();
  if (size != 6310088) return fail(error, "Tamanho diferente do banco PES3 conferido");
  std::vector<unsigned char> candidate(static_cast<std::size_t>(size));
  file.seekg(0);
  if (!file.read(reinterpret_cast<char*>(candidate.data()), candidate.size()))
    return fail(error, "Falha na leitura do banco PES3");
  if (crc32(candidate) != 0x353ff124u) return fail(error, "Banco PES3 alterado/corrompido");
  std::vector<Clip> directory;
  if (!inspect(candidate, directory, error) || directory.size() != 1105) return false;
  bytes.swap(candidate); clips.swap(directory);
  return true;
}
bool AnimationBank::sample(unsigned clip, float phase, Frame& out) const {
  if (clip >= clips.size() || !std::isfinite(phase)) return false;
  Frame candidate;
  auto& channels = candidate.channels;
  channels.channel_count = 19;
  for (unsigned i = 0; i < 19; ++i) {
    channels.bones[i].rotation_a[3] = channels.bones[i].rotation_b[3] = 1;
    for (unsigned axis = 0; axis < 4; ++axis)
      channels.bones[i].translation_a[axis] = channels.bones[i].translation_b[axis] =
          number(PES_SKELETON_TRANSLATION_BITS[i][axis]);
  }
  const auto& entry = clips[clip];
  if (pes_animation_channels_decode(bytes.data()+entry.offset, entry.bytes, phase, &channels) != 1 ||
      pes_animation_pose_evaluate(&channels, &candidate.local) != 1) return false;
  const int pairs[19] = {-1,-1,3,2,5,4,7,6,-1,10,9,12,11,14,13,-1,-1,18,17};
  // Format-2 decoder/evaluator retains the source 0x80 representation flag.
  candidate.rig.flags[1] = 0x81;
  for (unsigned i = 0; i < 19; ++i) {
    auto& bone = candidate.rig.bones[i];
    bone.parent = PES_SKELETON_PARENTS[i]; bone.mirror = pairs[i];
    for (unsigned axis = 0; axis < 4; ++axis) {
      bone.local_rotation[axis] = candidate.local.bones[i].rotation[axis];
      bone.local_translation[axis] = candidate.local.bones[i].translation[axis];
    }
  }
  try { pes3_pose::materialize(candidate.rig); pes3_pose::validate(candidate.rig); }
  catch (const std::exception&) { return false; }
  out = candidate;
  return true;
}
void Playback::advance(float dt, float rate, float duration) {
  if (!std::isfinite(dt) || !std::isfinite(rate) || !std::isfinite(duration) ||
      !std::isfinite(phase) || phase < 0 ||
      dt < 0 || rate <= 0 || duration <= 0) throw std::domain_error("invalid playback time");
  if (!playing) return;
  phase = std::min(duration, phase + dt*rate);
  if (phase >= duration) playing = false;
}
void Playback::step(float duration) {
  if (!std::isfinite(duration) || duration <= 0) throw std::domain_error("invalid duration");
  playing = false; phase = std::min(duration, phase + 1.0f);
}
} // namespace pes3
