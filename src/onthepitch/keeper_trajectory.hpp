#pragma once
#include <array>
#include <cmath>
namespace football_keeper {
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
