#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>

namespace football_reception {
using Vec=std::array<float,3>;
struct Plan {bool valid=false;float time=0,gap=0,height=0;Vec point{};};
// Scan the same future trajectory the real ball integrator uses, including
// bounces. A straight horizontal closest-point estimate misses arrivals that
// enter receiving height later, especially lofted and descending passes.
template<class Predictor> Plan predict(const Predictor &ball,Vec actor,Vec velocity,Vec ballVelocity,bool freeBall){
  Plan best;if(!freeBall)return best;
  const Vec now=ball(0);Vec relative{};float speed2=0,gap2=0,approach=0;
  for(unsigned i=0;i<3;++i){relative[i]=ballVelocity[i]-velocity[i];speed2+=relative[i]*relative[i];if(i<2){const float delta=now[i]-actor[i];gap2+=delta*delta;approach-=delta*relative[i];}}
  const float speed=std::sqrt(speed2),gap=std::sqrt(gap2);
  if(!std::isfinite(speed)||speed<.8f||speed>26.f||
     (approach/std::max(.1f,gap)<.15f&&!(relative[2]<-.8f&&gap<1.05f)))return best;
  float score=std::numeric_limits<float>::infinity();
  for(unsigned ms=40;ms<=900;ms+=20){const Vec p=ball(ms);const float time=ms*.001f;
    const float x=p[0]-actor[0]-velocity[0]*time,y=p[1]-actor[1]-velocity[1]*time,height=p[2]-actor[2];
    const float distance=std::sqrt(x*x+y*y);
    if(!std::isfinite(distance)||!std::isfinite(height)||distance>1.05f||height<.055f||height>2.35f)continue;
    const float rating=distance+.12f*time;
    if(rating<score){score=rating;best={true,time,distance,height,p};}
  }
  return best;
}
}
