#pragma once
#include "onthepitch/player/humanoid/physical_rig.hpp"
#include "onthepitch/player/humanoid/walking_gait.hpp"

namespace football_physics {
// World-space footstep plans drive joint muscles, never body transforms.
class SupportLocomotion {
 public:
  static Pose standing(const pes3::NativeBind &bind,Quat heading){
    Pose q=bind.rotations;q[0]=normalized(productRotation(heading,exponential({{.10f,0,0}})));
    q[7]=q[10]=exponential({{-.10f,0,0}});q[8]=q[11]=exponential({{.20f,0,0}});
    q[9]=q[12]=exponential({{-.20f,0,0}});q[4]=q[6]=exponential({{-.35f,0,0}});return q;
  }
  static void fk(const pes3::NativeBind &bind,float scale,const Pose &q,Vec root,Points &p,Pose &global){
    p[0]=root;for(unsigned i=0;i<13;++i){const int parent=pes3::nativeParents[i];
      global[i]=parent<0?q[i]:normalized(productRotation(global[parent],q[i]));
      if(parent>=0)p[i]=addPoint(p[parent],rotatePoint(global[parent],scalePoint(bind.offsets[i],scale)));}
  }
  static void leg(const pes3::NativeBind &bind,float scale,Pose &q,Vec root,unsigned side,Vec target,Quat sole){
    const unsigned hip=side?10:7,knee=hip+1,ankle=hip+2;Points p;Pose global;fk(bind,scale,q,root,p,global);
    const float a=length(subtractPoint(p[knee],p[hip])),b=length(subtractPoint(p[ankle],p[knee]));
    const Vec direction=unit(subtractPoint(target,p[hip]));
    const float distance=bounded(length(subtractPoint(target,p[hip])),std::fabs(a-b)+.003f,a+b-.004f);
    const Vec forward=rotatePoint(q[0],{{0,-1,0}}),pole=unit(subtractPoint(forward,scalePoint(direction,dotPoint(forward,direction))));
    const float along=(a*a-b*b+distance*distance)/(2*distance);
    const Vec bend=addPoint(addPoint(p[hip],scalePoint(direction,along)),scalePoint(pole,std::sqrt(std::max(0.f,a*a-along*along))));
    const Vec end=addPoint(p[hip],scalePoint(direction,distance));
    const Quat upper=normalized(productRotation(pes3::swingRotation(unit(subtractPoint(p[knee],p[hip])),unit(subtractPoint(bend,p[hip]))),global[hip]));
    q[hip]=normalized(productRotation(inverseRotation(q[0]),upper));fk(bind,scale,q,root,p,global);
    const Quat lower=normalized(productRotation(pes3::swingRotation(unit(subtractPoint(p[ankle],p[knee])),unit(subtractPoint(end,p[knee]))),global[knee]));
    q[knee]=normalized(productRotation(inverseRotation(global[hip]),lower));fk(bind,scale,q,root,p,global);
    q[ankle]=normalized(productRotation(inverseRotation(global[knee]),sole));
  }
  void initialize(const pes3::NativeBind &bind,float scale,Quat yaw,Vec root){
    heading=yaw;center=root;center[2]=.925f*scale;
    Pose global;Points p;fk(bind,scale,standing(bind,yaw),center,p,global);
    for(unsigned side=0;side<2;++side){anchor[side]=p[side?12:9];anchor[side][2]=.075f*scale;}
    nominal=subtractPoint(center,scalePoint(addPoint(anchor[0],anchor[1]),.5f));nominal[2]=0;
    phase=0;age=0;swing=1;ready=true;transferStart=center;
  }
  Pose step(const pes3::NativeBind &bind,float scale,const Pose &source,Vec actualRoot,Vec com,Vec velocity,
      const Points &actual,const std::array<bool,2> &contact,Vec command,float dt){
    age+=dt;command=capped(command,.4f);
    const bool walking=length(command)>.06f;
    if(!walking&&phase==0){
      center=addPoint(scalePoint(addPoint(anchor[0],anchor[1]),.5f),nominal);center[2]=.925f*scale;
    }else if(phase==0){phase=1;age=0;transferStart=center;}
    Vec feet[2]={anchor[0],anchor[1]};
    if(phase==1){
      const unsigned stance=1-swing;
      Vec goal=addPoint(anchor[stance],nominal);goal[2]=.925f*scale;
      center=addPoint(transferStart,scalePoint(subtractPoint(goal,transferStart),smooth(age/1.2f)));
      const Vec capture=addPoint(com,scalePoint(velocity,.20f));
      Vec gap=rotatePoint(inverseRotation(heading),subtractPoint(capture,anchor[stance]));
      if(age>1.2f&&std::fabs(rotatePoint(inverseRotation(heading),velocity)[0])<.03f&&contact[stance]&&std::fabs(gap[0])<.045f*scale){
        phase=2;age=0;swingStart=anchor[swing];
        Vec step=scalePoint(command,.4f);step=capped(step,.14f*scale);
        swingEnd=addPoint(addPoint(scalePoint(addPoint(anchor[0],anchor[1]),.5f),step),rotatePoint(heading,{{swing?-.087f*scale:.087f*scale,0,0}}));
        swingEnd[2]=.075f*scale;motionStart=center;
      }
    }
    if(phase==2){
      const float u=bounded(age/.50f,0,1),ease=u*u*u*(10+u*(-15+6*u));
      feet[swing]=addPoint(swingStart,scalePoint(subtractPoint(swingEnd,swingStart),ease));
      feet[swing][2]+=.040f*scale*std::pow(std::sin(3.14159265f*u),2.f);
      center=addPoint(motionStart,scalePoint(command,.20f*std::min(age,.50f)));center[2]=.925f*scale;
      if(age>.55f&&contact[swing]&&actual[swing?12:9][2]<.12f*scale){
        anchor[swing]=actual[swing?12:9];anchor[swing][2]=.075f*scale;
        feet[swing]=anchor[swing];swing=1-swing;phase=walking?1:0;age=0;transferStart=center;++steps;
      }
    }
    Pose target=standing(bind,heading);target[2]=source[2];
    if(phase)football_walk::upperBody(bind,target,float(steps)*.5f+(phase==2?.5f*bounded(age/.5f,0,1):0));
    // A stance target follows the measured sole. Keeping an old world-space
    // point while converting everything to joint angles loses translation
    // feedback: tiny contact slips then accumulate without a restoring step.
    for(unsigned side=0;side<2;++side)if(phase!=2||side!=swing){feet[side]=actual[side?12:9];feet[side][2]=.075f*scale;}
    for(unsigned side=0;side<2;++side)leg(bind,scale,target,center,side,feet[side],heading);
    return target;
  }
  unsigned phase=0,steps=0;float age=0;bool ready=false;
  Vec targetCenter()const{return center;}
 private:
  Quat heading{{0,0,0,1}};Vec center{},nominal{},anchor[2]{},transferStart{},swingStart{},swingEnd{},motionStart{};unsigned swing=1;
};
}
