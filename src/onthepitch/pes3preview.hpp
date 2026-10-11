#pragma once
#include "../pes3/animation_bank.hpp"
#include "scene/objects/geometry.hpp"
#include "scene/scene3d/node.hpp"
#include <array>

class PES3Preview {
 public:
  explicit PES3Preview(boost::intrusive_ptr<blunted::Node> target);
  std::string toggle();
  std::string select(int offset);
  std::string capturedClip();
  std::string pause();
  std::string step();
  void process(bool matchPaused);
  void prepare(const blunted::Vector3& playerPosition, const blunted::Vector3& direction);
  void fetch() { fetched = buffer; }
  void put();
 private:
  std::string caption() const;
  struct Snapshot {
    bool visible = false;
    std::array<blunted::Vector3,19> points;
    blunted::Vector3 position;
    blunted::Quaternion rotation;
    unsigned long revision = 0;
    unsigned clip = 0;
    float phase = 0;
  };
  pes3::AnimationBank bank;
  pes3::Playback playback;
  pes3::Frame pose;
  bool visible = false;
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
