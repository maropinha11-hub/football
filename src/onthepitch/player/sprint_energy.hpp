#pragma once
#include <algorithm>
#include <cmath>

namespace football_condition {
// Short anaerobic reserve, independent of the original match-long fatigue.
// One update per 10 ms player tick, never per animation candidate or render.
struct SprintEnergy {
  float value=1.f, recoveryDelay=0.f;
  bool depleted=false;
  float speedLimit(float normalMaximum)const {
    const float reserve=depleted?0.f:std::min(1.f,value/.24f);
    const float smooth=reserve*reserve*(3.f-2.f*reserve);
    return 4.35f+(std::max(4.35f,normalMaximum)-4.35f)*smooth;
  }
  void step(float dt,float speed,bool requested,float stamina,bool inPlay=true) {
    if(!std::isfinite(dt)||dt<=0||!std::isfinite(speed))return;
    dt=std::min(.05f,dt);stamina=std::max(0.f,std::min(1.f,stamina));
    const bool sprinting=inPlay&&requested&&!depleted&&speed>2.5f;
    if(sprinting){
      const float intensity=std::max(.45f,std::min(1.f,(speed-4.1f)/2.6f));
      value-=dt*intensity/(7.5f+3.5f*stamina);recoveryDelay=.8f;
      if(value<=.015f)depleted=true;
    }else{
      recoveryDelay=std::max(0.f,recoveryDelay-dt);
      // Standing/walking restores more reserve than jogging; no dependence
      // on accelerated match time, and no free refill at every restart.
      if(recoveryDelay==0)value+=dt*(speed<2.f?.095f:speed<4.5f?.055f:.020f);
    }
    value=std::max(0.f,std::min(1.f,value));
    // A partial refill is usable. Hysteresis prevents a zero-energy
    // sprint/jog switch on every frame when RB stays held.
    if(depleted&&(value>=.25f||(!requested&&value>=.10f)))depleted=false;
  }
};
}
