#pragma once
#include <algorithm>
#include <cmath>
namespace football_input {
constexpr float walkingStickLimit=.74f;
inline float movementSpeed(float strength,bool sprint,float normalMaximum,float sprintMaximum){
 strength=std::max(0.f,std::min(1.f,strength));
 if(strength<.001f)return 0;
 if(sprint)return strength*sprintMaximum;
 if(strength<=walkingStickLimit)return 1.55f*std::pow(strength/walkingStickLimit,.72f);
 const float t=(strength-walkingStickLimit)/(1-walkingStickLimit);
 const float eased=t*t*(3-2*t);
 return 1.55f+(normalMaximum-1.55f)*eased;
}
}
