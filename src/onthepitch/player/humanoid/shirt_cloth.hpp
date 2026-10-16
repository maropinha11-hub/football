#pragma once
#include "physical_rig.hpp"
#include <vector>

namespace football_physics {
// A bounded XPBD shell on the existing shirt mesh, with welded UV seams.
// Collar/arm/skin vertices remain pinned to the native animated surface.
class ShirtCloth {
 public:
  void configure(const std::vector<Vec>& rest,const std::vector<unsigned>& triangles,const std::vector<float>& mobility);
  void step(const std::vector<Vec>& target,const std::vector<Vec>& normal,float dt,Vec gripPoint,Vec gripForce);
  const std::vector<Vec>& positions()const{return displayed;}
  unsigned movable()const{return movableCount;}
  float displacement()const{return peakOffset;}
  float stretch()const{return peakStretch;}
  bool reportDue(unsigned long now){if(!lastReport || now<lastReport || now-lastReport>=100){lastReport=now;return true;}return false;}
 private:
  struct Edge {unsigned a,b;float lambda=0;};
  std::vector<unsigned> mapping;
  std::vector<Vec> x,velocity,displayed,previousTarget;
  std::vector<float> mobility;
  std::vector<Edge> edges;
  bool ready=false;
  unsigned movableCount=0;
  float peakOffset=0,peakStretch=0;
  unsigned long lastReport=0;
};
}
