#pragma once
// Source motion playback only. No guessed action names or native retarget.
#include "pes_animation_pose.h"
#include "../../tools/pes3/recovered/pose_rig.hpp"
#include <string>
#include <vector>

namespace pes3 {
struct Clip {
  unsigned offset = 0, bytes = 0;
  float duration = 0;
};
struct Frame {
  PesAnimationChannels channels{};
  PesLocalPose local{};
  pes3_pose::Rig rig{};
};
class AnimationBank {
 public:
  // Public inspection accepts structurally valid containers; load additionally
  // pins the received v0.14 bank's size/count/CRC. Failed loads clear the bank.
  static bool inspect(const std::vector<unsigned char>& data, std::vector<Clip>& clips,
                      std::string& error);
  bool load(const std::string& path, std::string& error);
  bool sample(unsigned clip, float phase, Frame& out) const;
  unsigned count() const { return clips.size(); }
  float duration(unsigned clip) const { return clips.at(clip).duration; }
 private:
  std::vector<unsigned char> bytes;
  std::vector<Clip> clips;
};
// Playback policy is explicit: one source clip clamps at its endpoint. Source
// phase units are not identified with 50/60 Hz or native simulation frames.
class Playback {
 public:
  unsigned clip = 0;
  float phase = 0;
  bool playing = true;
  void select(unsigned value) { clip = value; phase = 0; playing = true; }
  void advance(float dt, float unitsPerSecond, float duration);
  void step(float duration);
};
} // namespace pes3
