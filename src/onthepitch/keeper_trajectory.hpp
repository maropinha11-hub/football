#pragma once
#include <array>
#include <algorithm>
#include <cmath>
namespace football_keeper {
// A diving pose is useful when the ball arrives at its reaching plane, not
// merely because it will eventually cross the goal. Keep lateral reach and
// height in the animation solver; synchronize its preparation with flight.
inline bool saveWindow(float authoredForward,float predictedForward,float forwardSpeed){
 if(!std::isfinite(authoredForward)||!std::isfinite(predictedForward)||!std::isfinite(forwardSpeed))return false;
 return std::fabs(predictedForward-authoredForward)<=std::max(.50f,std::min(1.15f,std::fabs(forwardSpeed)*.065f));
}
inline float closeAngleDepth(float goalDistance,float attackerDistance,float defenderDistance){
 if(!std::isfinite(goalDistance)||!std::isfinite(attackerDistance)||!std::isfinite(defenderDistance)||attackerDistance>1.6f||goalDistance>24||goalDistance<1||defenderDistance<3)return 0;
 return std::max(1.5f,std::min(8.f,goalDistance*.43f));
}
inline bool goalCrossing(const std::array<float,3> &a,const std::array<float,3> &b,
                         float side,float line,float width,float height,float &y){
 const float before=a[0]*side-line,after=b[0]*side-line;
 if(!(before<=0&&after>0))return false;
 const float t=-before/(after-before),z=a[2]+t*(b[2]-a[2]);
 const float crossing=a[1]+t*(b[1]-a[1]);
 if(!std::isfinite(z)||!std::isfinite(crossing)||std::fabs(crossing)>width||z<-.11f||z>height)return false;
 y=crossing;return true;
}
}
