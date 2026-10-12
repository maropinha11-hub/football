#pragma once
#include "../pes3/animation_bank.hpp"
#include "../pes3/native_pose.hpp"
#include "../pes3/motion_match.hpp"
#include "scene/objects/geometry.hpp"
#include "scene/scene3d/node.hpp"
#include <array>
#include <map>
#include <tuple>
namespace blunted { class Animation; }

class PES3Preview {
 public:
  explicit PES3Preview(boost::intrusive_ptr<blunted::Node> target);
  std::string toggle();
  std::string select(int offset);
  std::string capturedClip();
  std::string pause();
  std::string step();
  std::string toggleBody();
  void releaseBodyForGameplay();
  bool studyingBody() const { return visible && bodyEnabled; }
  bool bodyPose(const pes3::NativeBind& reference,pes3::NativePose& out) const;
  bool livePose(blunted::Animation* animation,int frame,int touchFrame,int function,
                const pes3::NativeBind& reference,pes3::NativePose& out);
  void process(bool matchPaused);
  void prepare(const blunted::Vector3& playerPosition, const blunted::Vector3& direction);
  void fetch() { fetched = buffer; }
  void put();
 private:
  std::string caption() const;
  struct Snapshot {
    bool visible = false;
    bool body = false;
    std::array<blunted::Vector3,19> points;
    pes3::SourceRotations rotations{};
    blunted::Vector3 position;
    blunted::Quaternion rotation;
    unsigned long revision = 0;
    unsigned clip = 0;
    float phase = 0;
  };
  pes3::AnimationBank bank;
  pes3::MotionMatcher matcher;
  bool liveInitialized=false,liveAvailable=false;
  using LiveKey=std::tuple<const blunted::Animation*,int,int>;
  std::map<LiveKey,pes3::MotionChoice> liveChoices;
  LiveKey lastLiveKey{};
  int lastLiveFrame=-1,transitionStart=0;
  bool haveLivePose=false;
  bool transitionActive=false;
  pes3::NativePose previousLivePose{},transitionPose{};
  pes3::Playback playback;
  pes3::Frame pose;
  bool visible = false;
  bool bodyEnabled = false;
  pes3::SourceRotations referenceRotations{};
  pes3::SourcePoints referencePoints{};
  bool poseDirty = true;
  float rate = 60;
  unsigned capturedIndex = 0;
  unsigned long revision = 0, renderedRevision = 0;
  unsigned renderedClip = ~0u;
  std::string loadError;
  Snapshot buffer, fetched;
  boost::intrusive_ptr<blunted::Geometry> geometry;
  blunted::Material material;
};
