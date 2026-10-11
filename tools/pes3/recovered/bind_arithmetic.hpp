#pragma once
// Explicit finite binary32 profiles for source-model initialization.
// No process/global rounding-mode changes. COP1 division/sqrt remain nearest.
#include "pose_rig.hpp"

namespace pes3_pose {
struct BindArithmetic {
  bool chop=false;
  float rounded(double exact) const {
    float result=static_cast<float>(exact);
    if(!std::isfinite(result)) throw std::domain_error("finite bind arithmetic required");
    if(chop && std::abs(static_cast<double>(result))>std::abs(exact)) {
      std::uint32_t raw;std::memcpy(&raw,&result,4);--raw;std::memcpy(&result,&raw,4);
    }
    return result;
  }
  float va(float a,float b) const {return vu(rounded(static_cast<double>(vu(a))+vu(b)));}
  float vs(float a,float b) const {return vu(rounded(static_cast<double>(vu(a))-vu(b)));}
  float vm(float a,float b) const {return vu(rounded(static_cast<double>(vu(a))*vu(b)));}
  float fa(float a,float b) const {return rounded(static_cast<double>(a)+b);}
  float fs(float a,float b) const {return rounded(static_cast<double>(a)-b);}
  float fm(float a,float b) const {return rounded(static_cast<double>(a)*b);}
  float divide(float a,float b) const {return pes3_pose::fd(a,b);}
  Vector quaternion(const Matrix& m) const {
    if(!chop)return matrix_quaternion(m);
    const float trace=fa(1,fa(m[2][2],fa(m[0][0],m[1][1])));
    Vector q{};
    if(trace>0.1f) {
      const float s=fp(static_cast<float>(std::sqrt(static_cast<double>(trace))));
      q[3]=divide(s,2);const float factor=divide(0.5f,s);
      q[0]=fm(factor,fs(m[1][2],m[2][1]));
      q[1]=fm(factor,fs(m[2][0],m[0][2]));
      q[2]=fm(factor,fs(m[0][1],m[1][0]));
    } else {
      unsigned i=m[0][0]<m[1][1]?1:0;if(m[i][i]<m[2][2])i=2;
      const unsigned j=(i+1)%3,k=(i+2)%3;
      const float square=fa(1,fs(fs(m[i][i],m[j][j]),m[k][k]));
      float s=fp(static_cast<float>(std::sqrt(static_cast<double>(square))));
      q[i]=divide(s,2);if(s!=0)s=divide(.5f,s);
      if(i==0) {
        q[1]=fm(s,fa(m[0][1],m[1][0]));q[2]=fm(s,fa(m[2][0],m[0][2]));q[3]=fm(s,fs(m[1][2],m[2][1]));
      } else if(i==1) {
        q[0]=fm(s,fa(m[0][1],m[1][0]));q[2]=fm(s,fa(m[1][2],m[2][1]));q[3]=fm(s,fs(m[2][0],m[0][2]));
      } else {
        q[0]=fm(s,fa(m[2][0],m[0][2]));q[1]=fm(s,fa(m[1][2],m[2][1]));q[3]=fm(s,fs(m[0][1],m[1][0]));
      }
    }
    return q;
  }
  Vector product(Vector a,Vector b) const {
    Vector out{};
    out[3]=vs(vs(vs(vm(a[3],b[3]),vm(a[0],b[0])),vm(a[1],b[1])),vm(a[2],b[2]));
    for(unsigned lane=0;lane<3;++lane) {
      const unsigned i=(lane+1)%3,j=(lane+2)%3;
      const float cross=vs(vm(a[i],b[j]),vm(b[i],a[j]));
      out[lane]=va(va(vm(a[lane],b[3]),vm(b[lane],a[3])),vm(cross,1));
    }
    return out;
  }
};
} // namespace pes3_pose
