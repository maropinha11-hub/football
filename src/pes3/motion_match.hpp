#pragma once
// FPSoccer's hybrid motion matcher, not the recovered PES action selector.
// Native gameplay chooses the action and its contact; source poses supply
// compatible visual motion. No PES clip ID is assigned a guessed action name.
#include "animation_bank.hpp"
#include "native_pose.hpp"
#include <vector>

namespace pes3 {
constexpr unsigned trajectorySamples=9;
using Trajectory=std::array<NativePose,trajectorySamples>;
struct MotionRequest {
  Trajectory poses{};
  float contact=-1; // Native normalized timeline, -1 for no contact.
  int contactBone=-1; // Native ankle 9/12 or head 2; never a PES action ID.
};
struct MotionChoice {
  bool accepted=false;
  unsigned clip=0;
  float sourceContact=.5f;
  float error=0;
  bool mirrored=false;
};
// Both clock segments meet exactly at the native event. Native physics is
// unchanged; source phase units are not interpreted as frames or seconds.
float warpPhase(float time,float nativeContact,float sourceContact);
bool rebuildPose(const NativeBind& bind,NativePose& pose,bool groundSupport);
bool blendPose(const NativeBind& bind,const NativePose& a,const NativePose& b,
               float weight,NativePose& out,bool groundSupport=true);
// Native anatomical reflection for this adapter; not the recovered PES
// source-rig mirror routine. The native foot's quality and events stay native.
bool mirrorPose(const NativeBind& bind,const NativePose& pose,NativePose& out);
class MotionMatcher {
 public:
  bool initialize(const AnimationBank& bank,const NativeBind& bind);
  MotionChoice choose(const MotionRequest& request) const;
  bool sample(const MotionChoice& choice,float time,float nativeContact,NativePose& out) const;
  unsigned candidates() const { return library.size(); }
 private:
  struct Candidate { unsigned clip; std::array<NativePose,17> poses; };
  bool retarget(unsigned clip,float phase,NativePose& out) const;
  const AnimationBank* bank=nullptr;
  NativeBind bind{};
  SourceRotations reference{};
  SourcePoints referencePoints{};
  std::vector<Candidate> library;
};
} // namespace pes3
