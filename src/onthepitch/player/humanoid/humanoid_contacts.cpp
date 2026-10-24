// Contacts on the same weighted skin and native skeleton used for rendering.
#include "humanoidbase.hpp"
#include "situational_action.hpp"
#include "anatomical_arms.hpp"
#include "native_contact_timing.hpp"
#include "../../match.hpp"
#include "../player.hpp"
#include "../controller/humancontroller.hpp"
#include "../../../main.hpp"
#include "humanoid_utils.hpp"
#include "utils/animationextensions/footballanimationextension.hpp"
#include <cmath>
#include <limits>

namespace {
std::string skinPart(const std::string &part) {
  if(part=="left_foot")return "left_ankle";
  if(part=="right_foot")return "right_ankle";
  if(part=="head")return "neck";
  if(part=="torso" || part=="body" || part=="trunk" || part=="pelvis")return "middle";
  if(part=="left_upperleg")return "left_thigh";
  if(part=="right_upperleg")return "right_thigh";
  if(part=="left_lowerleg")return "left_knee";
  if(part=="right_lowerleg")return "right_knee";
  if(part=="left_upperarm")return "left_shoulder";
  if(part=="right_upperarm")return "right_shoulder";
  if(part=="left_lowerarm")return "left_elbow";
  if(part=="right_lowerarm")return "right_elbow";
  return part;
}
Quaternion rotationBetween(const Vector3 &from,const Vector3 &to) {
  const Vector3 a=from.GetNormalized(0),b=to.GetNormalized(0);
  const Vector3 axis=a.GetCrossProduct(b);
  return Quaternion(axis.coords[0],axis.coords[1],axis.coords[2],1+a.GetDotProduct(b)).GetNormalized();
}
float ease(float t) {t=clamp(t,0.0f,1.0f);return t*t*(3-2*t);}
Vector3 triangleClosest(const Vector3 &p,const Vector3 *t) {
  Vector3 result=t[0];float best=(p-result).GetLength();
  auto consider=[&](const Vector3 &q){const float d=(p-q).GetLength();if(d<best){best=d;result=q;}};
  const Vector3 ab=t[1]-t[0],ac=t[2]-t[0],ap=p-t[0];
  const float aa=ab.GetDotProduct(ab),bb=ac.GetDotProduct(ac),cross=ab.GetDotProduct(ac);
  const float det=aa*bb-cross*cross;
  if(det>1e-12f) {
    const float pa=ap.GetDotProduct(ab),pb=ap.GetDotProduct(ac);
    const float u=(pa*bb-pb*cross)/det,v=(pb*aa-pa*cross)/det;
    if(u>=0 && v>=0 && u+v<=1)consider(t[0]+ab*u+ac*v);
  }
  for(unsigned e=0;e<3;++e) {
    const Vector3 d=t[(e+1)%3]-t[e];const float sq=d.GetDotProduct(d);
    consider(t[e]+d*(sq>1e-12f?clamp((p-t[e]).GetDotProduct(d)/sq,0.0f,1.0f):0));
  }
  return result;
}
}

bool HumanoidBase::UsesTrainingContacts() const {
  return TrainingEnabled() && (!PlayerMatchEnabled() || match->GetTrainingPlayer()==player || PhysicalRigEnabled());
}

bool HumanoidBase::TackleLegContact(const HumanoidBase &victim,Vector3 &point)const {
  if((!UsesTrainingContacts()&&!PhysicalRigEnabled()) ||
     (!victim.UsesTrainingContacts()&&!victim.PhysicalRigEnabled()))return false;
  // Simulation skeletons, rather than renderer-thread AABBs. Probe the shoe
  // and shin capsules along their lengths; only lower limbs can trip a leg.
  float best=100.f;Vector3 hit;
  for(unsigned ankle:{9u,12u})for(unsigned other:{9u,12u}){
    const auto &lo=pes3NativeReference.footMin[ankle==12],&hi=pes3NativeReference.footMax[ankle==12];
    const Vector3 toe=contactPositions[ankle]+contactGlobal[ankle]*
      Vector3((lo[0]+hi[0])*.5f,lo[1],(lo[2]+hi[2])*.5f)*zMultiplier;
    const Vector3 own[5]={toe,contactPositions[ankle],contactPositions[ankle-1],contactPositions[ankle-2],contactPositions[0]};
    const Vector3 a=victim.contactPositions[other],b=victim.contactPositions[other-1];
    const unsigned segments=currentAnim->functionType==e_FunctionType_Sliding?4:2;
    for(unsigned segment=0;segment<segments;++segment)for(unsigned sample=0;sample<=12;++sample){
      const Vector3 p=own[segment]+(own[segment+1]-own[segment])*(sample/12.f);
      const Vector3 axis=b-a;
      const Vector3 q=a+axis*clamp((p-a).GetDotProduct(axis)/std::max(.00001f,axis.GetSquaredLength()),0.f,1.f);
      const float d=(p-q).GetLength();
      if(d<best){best=d;hit=(p+q)*.5f;}
    }
  }
  if(GetConfiguration()->GetBool("training_telemetry",false) && match->GetActualTime_ms()%50==0)
    printf("TACKLE_LEG_PROBE t=%lu actor=%d victim=%d gap=%.5f frame=%d\n",match->GetActualTime_ms(),player->GetID(),victim.player->GetID(),best,currentAnim->frameNum);
  point=hit;return best<.13f;
}

void HumanoidBase::CaptureContactMesh() {
  if(PlayerMatchEnabled() && !UsesTrainingContacts() && !PhysicalRigEnabled())return;
  contactJointBone.fill(-1);
  for(unsigned j=0;j<joints.size();++j)for(unsigned i=0;i<13;++i)
    if(joints[j].node->GetName()==pes3::nativeBoneNames[i])contactJointBone[j]=int(i);
  auto geometry=boost::static_pointer_cast<Geometry>(fullbodyNode->GetObject("fullbody"))->GetGeometryData();
  geometry->resourceMutex.lock();
  const auto &meshes=geometry->GetResource()->GetTriangleMeshesRef();
  for(unsigned m=0;m<meshes.size();++m) {
    const auto &indices=meshes[m].indices;
    for(unsigned t=0;t+2<indices.size();t+=3) {
      float weights[13]={};
      for(unsigned c=0;c<3;++c)for(const auto &b:weightedVerticesVec[m][indices[t+c]].bones) {
        const int bone=contactJointBone[b.jointID];if(bone>=0)weights[bone]+=b.weight;
      }
      const unsigned dominant=std::max_element(weights,weights+13)-weights;
      const std::string part=dominant<=1?"middle":pes3::nativeBoneNames[dominant];
      if(!part.empty())contactTriangles.push_back({m,{{indices[t],indices[t+1],indices[t+2]}},part});
    }
  }
  geometry->resourceMutex.unlock();
  if(UsesTrainingContacts())for(Animation *animation:anims->GetAnimations()) {
    if(animation->GetVariable("training_dribble")!="true")continue;
    for(int frame=0;frame<animation->GetFrameCount();++frame) {
      Quaternion local[13],global[13],unused;Vector3 positions[13],root;
      animation->GetKeyFrame("player",frame,unused,root);
      SampleContactAnimation(animation,float(frame),root,0,false,local,global,positions);
      float lowest=100;
      for(unsigned side=0;side<2;++side) {
        const auto &lo=pes3NativeReference.footMin[side],&hi=pes3NativeReference.footMax[side];
        const unsigned ankle=side?12:9;
        for(unsigned mask=0;mask<8;++mask) {
          Vector3 p(mask&1?hi[0]:lo[0],mask&2?hi[1]:lo[1],mask&4?hi[2]:lo[2]);
          lowest=std::min(lowest,(positions[ankle]+global[ankle]*p*zMultiplier).coords[2]);
        }
      }
      root.coords[2]+=(.005f-lowest)/zMultiplier;
      animation->SetKeyFrame("player",frame,unused,root);
    }
  }

  // Bind each event to this player's weighted skin. The old markers describe
  // proxy body parts; the native approach solver can now aim at the real mesh.
  if(UsesTrainingContacts())for(Animation *animation:anims->GetAnimations()) {
    auto extension=boost::static_pointer_cast<FootballAnimationExtension>(animation->GetExtension("football"));
    const std::string part=animation->GetVariable("touch_bodypart");
    if(!extension || part.empty() || extension->GetTouchCount()==0)continue;
    if(animation->GetAnimType()=="deflect"&&animation->GetVariable("keeper_authored_side").empty()){
      Vector3 original;int frame;
      if(extension->GetFirstTouch(original,frame))animation->SetVariable("keeper_authored_side",real_to_str(original.coords[0]));
    }
    for(auto &entry:extension->GetAnimation()) {
      Quaternion local[13],global[13];Vector3 positions[13],root;Quaternion unused;
      animation->GetKeyFrame("player",entry.first,unused,root);
      SampleContactAnimation(animation,float(entry.first),root,0,false,local,global,positions);
      if(part.find("foot")!=std::string::npos&&(animation->GetAnimType()=="shortpass"||animation->GetAnimType()=="longpass"||animation->GetAnimType()=="highpass"||animation->GetAnimType()=="shot")){
        const Vector3 direction=GetVectorFromString(animation->GetVariable("balldirection")).Get2D().GetNormalized(0);
        const Vector3 forward=(global[0]*Vector3(0,-1,0)).Get2D().GetNormalized(0);
        if(direction.GetDotProduct(forward)<-.55f)animation->SetVariable("physical_heel","true");
      }
      if(animation->GetVariable("added_chest")=="true") {
        // Fold the authored pelvis rotation into the spine, just as the live
        // upper layer does. Bind against upright locomotion hips, not the
        // full-body FBX's displaced chest joint.
        local[1]=(local[0]*local[1]).GetNormalized();local[0]=QUATERNION_IDENTITY;
        ContactForwardKinematics(local,global,positions);
      }
      Vector3 probe=entry.second.position;probe.coords[2]*=zMultiplier;
      const std::string technique=animation->GetVariable("physical_technique");
      if(!technique.empty() && part.find("foot")!=std::string::npos){
        const unsigned ankle=part=="right_foot"?12:9;const float side=part=="right_foot"?1.f:-1.f;
        const Vector3 face=technique=="inside"?Vector3(side*.45f,0,0):technique=="outside"?Vector3(-side*.45f,0,0):Vector3(0,-.45f,0);
        const float height=probe.coords[2];probe=positions[ankle]+global[ankle]*face;probe.coords[2]=height;
      }
      if(animation->GetVariable("physical_heel")=="true") {
        // A rear pass contacts the heel side of the shoe. Projecting an old
        // proxy marker onto its toe made the preparation step hit the ball
        // before the intended back-swing. Let the native whole-body approach
        // aim the real heel at the ball; do not enlarge the contact window.
        const unsigned ankle=part=="left_foot"?9:12;
        const Vector3 outward=GetVectorFromString(animation->GetVariable("balldirection")).Get2D().GetNormalized(Vector3(0,1,0));
        const float height=probe.coords[2];
        probe=positions[ankle]+outward*.45f;probe.coords[2]=height;
      }
      if(animation->GetVariable("training_dribble")=="true") {
        const unsigned ankle=part=="left_foot"?9:12;
        probe=positions[ankle]+Vector3(0,-.45f,0);probe.coords[2]=.11f;
      }
      const bool chest=animation->GetAnimType()=="trap" &&
        (animation->GetName().find("chest")!=std::string::npos || animation->GetVariable("added_chest")=="true");
      if(chest)probe=positions[1]+global[1]*Vector3(0,-.4f,.30f)*zMultiplier;
      Vector3 surface;if(ContactSurface(probe,chest?"chest":part,global,positions,&surface)>50)continue;
      const Vector3 normal=(probe-surface).GetNormalized(Vector3(0,-1,0));
      Vector3 point=surface+normal*.1105f;
      const std::string type=animation->GetAnimType();
      if(part.find("foot")!=std::string::npos &&
          (type=="shot" || type=="pass" || type=="shortpass" || type=="longpass" || type=="highpass")) {
        // Keep the authored ball height. A radial projection from a sloped
        // shoe can raise a ground-ball marker, making a valid side kick miss.
        Vector3 origin=surface;origin.coords[2]=probe.coords[2];
        const Vector3 outward=normal.Get2D().GetNormalized(Vector3(0,-1,0));
        float low=0,high=.35f;
        if(ContactSurface(origin,part,global,positions)<.0005f &&
            ContactSurface(origin+outward*high,part,global,positions)>.0005f) {
          for(unsigned step=0;step<12;++step) {
            const float middle=(low+high)*.5f;
            if(ContactSurface(origin+outward*middle,part,global,positions)>.0005f)high=middle;else low=middle;
          }
          point=origin+outward*((low+high)*.5f);
        }
      }
      point.coords[2]/=zMultiplier;
      entry.second.position=point;
    }
  }

}

void HumanoidBase::ContactForwardKinematics(Quaternion *local,Quaternion *global,Vector3 *positions) const {
  for(unsigned i=0;i<13;++i) {
    global[i]=(i?global[pes3::nativeParents[i]]*local[i]:local[i]).GetNormalized();
    if(i) {
      const auto &p=pes3NativeReference.offsets[i];
      positions[i]=positions[pes3::nativeParents[i]]+global[pes3::nativeParents[i]]*Vector3(p[0],p[1],p[2])*zMultiplier;
    }
  }
}

void HumanoidBase::BlendUpperReception(Animation *clip,float phase,float weight,radian facing,Quaternion *local,float armWeight) const {
  if(!clip || weight<=0)return;
  Quaternion source[7];Vector3 position;
  for(unsigned i=0;i<7;++i) {
    const int frame=int(phase),next=std::min(frame+1,clip->GetFrameCount()-1);
    Quaternion a,b;clip->GetKeyFrame(pes3::nativeBoneNames[i],frame,a,position);
    clip->GetKeyFrame(pes3::nativeBoneNames[i],next,b,position);
    source[i]=a.GetSlerped(phase-frame,b).GetNormalized();
  }
  if(PhysicalRigEnabled() && GetConfiguration()->GetBool("training_situational_motion",true)){
    std::array<pes3::Rotation,7> pose;
    for(unsigned i=0;i<7;++i)for(unsigned j=0;j<4;++j)pose[i][j]=source[i].elements[j];
    const float contact=std::atof(clip->GetVariable("touchframe").c_str());
    const float lateral=spatialState.bodyDirectionVec.GetRotated2D(-.5f*pi).GetDotProduct(match->GetBall()->GetMovement());
    football_situations::adaptChestArms(pose,phase,contact,float(clip->GetFrameCount()-1),spatialState.movement.GetLength(),lateral);
    for(unsigned i=3;i<7;++i)source[i]=Quaternion(pose[i][0],pose[i][1],pose[i][2],pose[i][3]);
  }
  // Chest reception faces its arrival axis, even while the legs retreat.
  if(player==match->GetTrainingPlayer())facing=match->GetTrainingReceptionFacing().GetAngle2D()+.5f*pi;
  Quaternion turn;turn.SetAngleAxis(facing,Vector3(0,0,1));
  source[1]=(local[0].GetInverse()*turn*source[0]*source[1]).GetNormalized();
  for(unsigned i=1;i<7;++i) {
    const float blend=i<3?weight:(armWeight<0?weight:armWeight);
    local[i]=local[i].GetSlerped(blend,source[i]).GetNormalized();
  }
}

void HumanoidBase::TickUpperReception() {
  if(!upperReceptionClip)return;
  if(PhysicalRigEnabled() && !upperReceptionTouchMade && player->GetExternalController() &&
      static_cast<HumanController*>(player->GetExternalController())->GetActionMode()!=0){
    // An explicit one-touch pass/shot owns the incoming ball. Do not let an
    // anticipatory chest layer consume it before the native action can fit.
    upperReceptionClip=nullptr;upperReceptionWeight=upperReceptionArmWeight=0;return;
  }
  upperReceptionPhase=float(match->GetActualTime_ms()-upperReceptionStarted_ms)*.1f;
  if(!upperReceptionTouchMade && upperReceptionPhase>upperReceptionContactFrame+7)
    upperReceptionEndFrame=std::min(upperReceptionEndFrame,upperReceptionContactFrame+19);
  if(upperReceptionPhase>=upperReceptionEndFrame) {
    if(GetConfiguration()->GetBool("training_telemetry",false))
      printf("TRAINING_UPPER_END t=%lu touched=%d phase=%.2f\n",match->GetActualTime_ms(),upperReceptionTouchMade?1:0,upperReceptionPhase);
    upperReceptionClip=nullptr;upperReceptionWeight=0;return;
  }
  upperReceptionWeight=ease(upperReceptionPhase/10)*ease((upperReceptionEndFrame-upperReceptionPhase)/12);
  if(upperReceptionTouchMade && upperReceptionArmRelease<0 && match->GetBall()->Predict(0).coords[2]<=.16f)
    upperReceptionArmRelease=upperReceptionPhase;
  upperReceptionArmWeight=upperReceptionWeight*(upperReceptionArmRelease<0?1:1-ease((upperReceptionPhase-upperReceptionArmRelease)/12));
  if(GetConfiguration()->GetBool("training_telemetry",false) && match->GetActualTime_ms()%100==0)
    printf("TRAINING_UPPER_STATE t=%lu phase=%.3f weight=%.5f touched=%d base_function=%d\n",
      match->GetActualTime_ms(),upperReceptionPhase,upperReceptionWeight,upperReceptionTouchMade?1:0,int(currentAnim->functionType));
}

bool HumanoidBase::StartUpperReception(Animation *clip,int contactFrame) {
  if(UpperReceptionActive() || contactFrame<1)return false;
  if(PhysicalRigEnabled() && player->GetExternalController() &&
      static_cast<HumanController*>(player->GetExternalController())->GetActionMode()!=0)return false;
  Quaternion local[13],global[13];Vector3 positions[13];
  // Judge the composed contact pose rather than the full-body FBX path.
  // Start anticipation only when its authored marker meets the trajectory.
  const Vector3 root=spatialState.position+spatialState.movement*(contactFrame*.01f);
  SampleContactAnimation(currentAnim->anim,float(currentAnim->frameNum),root,spatialState.angle,false,local,global,positions);
  BlendUpperReception(clip,float(contactFrame),1,spatialState.angle,local);
  ContactForwardKinematics(local,global,positions);
  const float gap=ContactSurface(match->GetBall()->Predict(contactFrame*10),"chest",global,positions);
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("TRAINING_UPPER_PLAN t=%lu gap=%.5f accepted=%d mode=%s\n",match->GetActualTime_ms(),gap,gap<=.025f?1:0,clip->GetVariable("reception_mode").c_str());
  if(gap>.025f)return false;
  upperReceptionClip=clip;upperReceptionContactFrame=contactFrame;upperReceptionEndFrame=clip->GetFrameCount()-1;
  upperReceptionStarted_ms=match->GetActualTime_ms();upperReceptionPhase=0;upperReceptionWeight=0;upperReceptionArmWeight=0;upperReceptionArmRelease=-1;upperReceptionTouchMade=false;
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("TRAINING_UPPER_START t=%lu mode=%s contact_frame=%d frames=%d legs_free=1\n",match->GetActualTime_ms(),
      clip->GetVariable("reception_mode").c_str(),contactFrame,clip->GetFrameCount());
  return true;
}

void HumanoidBase::PutUpperReception() {
  const auto &buffer=fetchedbuf_animApplyBuffer;
  if(!buffer.upperReception || buffer.upperWeight<=0)return;
  humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
  Vector3 legs[6];for(unsigned i=0;i<6;++i)legs[i]=nodeMap.at(pes3::nativeBoneNames[i+7])->GetDerivedPosition();
  const Vector3 root=nodeMap.at("body")->GetDerivedPosition();
  const Quaternion spine=nodeMap.at("middle")->GetRotation();
  Quaternion arms[4];for(unsigned i=0;i<4;++i)arms[i]=nodeMap.at(pes3::nativeBoneNames[i+3])->GetRotation();
  Quaternion local[13];
  for(unsigned i=0;i<13;++i)local[i]=nodeMap.at(pes3::nativeBoneNames[i])->GetRotation();
  local[0]=nodeMap.at("body")->GetDerivedRotation();
  // Fetch the composed physical upper pose at the same historical time as
  // the ball. Re-applying the latest source phase before a second render-only
  // smoother makes contact timing depend on frame rate.
  const Quaternion physicalSpine=fetchedContactLocal[0]*fetchedContactLocal[1];
  const Quaternion targetSpine=(local[0].GetInverse()*physicalSpine).GetNormalized();
  local[1]=local[1].GetSlerped(buffer.upperWeight,targetSpine).GetNormalized();
  local[2]=local[2].GetSlerped(buffer.upperWeight,fetchedContactLocal[2]).GetNormalized();
  for(unsigned i=3;i<7;++i)local[i]=local[i].GetSlerped(buffer.upperArmWeight,fetchedContactLocal[i]).GetNormalized();
  for(unsigned i=1;i<7;++i)nodeMap.at(pes3::nativeBoneNames[i])->SetRotation(local[i],false);
  humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
  if(GetConfiguration()->GetBool("training_telemetry",false)) {
    float legError=0,spineDelta=0,armError=0;
    for(unsigned i=0;i<4;++i)for(unsigned c=0;c<4;++c)armError=std::max(armError,std::fabs(arms[i].elements[c]-nodeMap.at(pes3::nativeBoneNames[i+3])->GetRotation().elements[c]));
    for(unsigned i=0;i<6;++i)legError=std::max(legError,(legs[i]-nodeMap.at(pes3::nativeBoneNames[i+7])->GetDerivedPosition()).GetLength());
    for(unsigned i=0;i<4;++i)spineDelta+=std::fabs(spine.elements[i]-local[1].elements[i]);
    printf("TRAINING_UPPER_MASK t=%lu phase=%.3f legs_error=%.8f root_error=%.8f spine_delta=%.6f arms_error=%.8f arm_weight=%.5f\n",buffer.snapshotTime_ms,
      buffer.upperPhase,legError,(root-nodeMap.at("body")->GetDerivedPosition()).GetLength(),spineDelta,armError,buffer.upperArmWeight);
  }
}

void HumanoidBase::SampleContactAnimation(const Animation *animation,float phase,const Vector3 &root,
    radian facing,bool source,Quaternion *local,Quaternion *global,Vector3 *positions) const {
  phase=clamp(phase,0.0f,float(animation->GetEffectiveFrameCount()));
  const int frame=int(phase),next=std::min(frame+1,animation->GetEffectiveFrameCount());
  Quaternion a,b;Vector3 p,q;
  animation->GetKeyFrame("player",frame,a,p);animation->GetKeyFrame("player",next,b,q);
  positions[0]=root.Get2D()+Vector3(0,0,((1-(phase-frame))*p.coords[2]+(phase-frame)*q.coords[2]+(source?0:.96f))*zMultiplier);
  for(unsigned i=0;i<13;++i) {
    animation->GetKeyFrame(pes3::nativeBoneNames[i],frame,a,p);
    animation->GetKeyFrame(pes3::nativeBoneNames[i],next,b,q);
    local[i]=a.GetSlerped(phase-frame,b).GetNormalized();
    if(!source && animation->GetAnimType()=="movement") {
      const auto offset=offsets.find(pes3::nativeBoneNames[i]);
      if(offset!=offsets.end()) {
        const auto &v=offset->second;
        local[i]=local[i].GetSlerped(v.bias,v.isRelative?v.orientation*local[i]:v.orientation).GetNormalized();
      }
    }
    if(i==0){Quaternion turn;turn.SetAngleAxis(facing,Vector3(0,0,1));local[i]=turn*local[i];}
  }
  if(!source && animation->GetVariable("added_chest")!="true")
    BlendUpperReception(upperReceptionClip,upperReceptionPhase,upperReceptionWeight,facing,local,upperReceptionArmWeight);
  ContactForwardKinematics(local,global,positions);
  if(PhysicalRigEnabled()&&animation->GetAnimType()=="deflect"){
    // Save markers and reach planning must use the same anatomical arms as
    // the active rig and renderer. Projecting only after selection moved a
    // correctly timed hand away from the ball by several centimetres.
    football_physics::Pose constrained;
    for(unsigned bone=0;bone<13;++bone)for(unsigned axis=0;axis<4;++axis)constrained[bone][axis]=local[bone].elements[axis];
    football_physics::Metrics metrics;
    football_physics::constrainArmPose(pes3NativeReference,zMultiplier,constrained,
      {{positions[0].coords[0],positions[0].coords[1],positions[0].coords[2]}},metrics);
    for(unsigned bone=0;bone<13;++bone)local[bone]=Quaternion(constrained[bone][0],constrained[bone][1],constrained[bone][2],constrained[bone][3]);
    ContactForwardKinematics(local,global,positions);
  }
  if(UsesTrainingContacts() && player->GetExternalController()) {
    const Quaternion authored=local[2];
    AimTrainingHead(local,global,positions,match->GetTrainingLookDirection());
    if(source && animation==chestAnimation.get()) {
      local[2]=authored.GetSlerped(ease((phase-chestContactFrame-5)/20),local[2]).GetNormalized();
      ContactForwardKinematics(local,global,positions);
    }
  }
}

float HumanoidBase::ContactSurface(const Vector3 &point,const std::string &requested,const Quaternion *global,
    const Vector3 *positions,Vector3 *closest,std::string *hitPart) const {
  const std::string part=skinPart(requested);
  float best=100;
  for(const auto &triangle:contactTriangles) {
    if(!part.empty() && triangle.part!=(part=="chest"?"middle":part))continue;
    if(part=="chest") {
      float bindHeight=0,bindForward=0;
      for(unsigned c=0;c<3;++c) {
        bindHeight+=uniqueFullbodyMesh[triangle.mesh].data[triangle.vertices[c]*3+2]/(3*zMultiplier);
        bindForward-=uniqueFullbodyMesh[triangle.mesh].data[triangle.vertices[c]*3+1]/(3*zMultiplier);
      }
      if(bindHeight<1.23f || bindHeight>1.52f || bindForward<.015f)continue;
    }
    Vector3 points[3];
    for(unsigned c=0;c<3;++c) {
      const auto &v=weightedVerticesVec[triangle.mesh][triangle.vertices[c]];
      const float *data=&uniqueFullbodyMesh[triangle.mesh].data[v.vertexID*3];
      const Vector3 original(data[0],data[1],data[2]);
      points[c]=Vector3(0);
      for(const auto &b:v.bones) {
        const int i=contactJointBone[b.jointID];if(i<0)continue;
        points[c]+=(global[i]*(original-joints[b.jointID].origPos*zMultiplier)+positions[i])*b.weight;
      }
    }
    const Vector3 surface=triangleClosest(point,points);
    const float d=(point-surface).GetLength();
    if(d<best){best=d;if(closest)*closest=surface;if(hitPart)*hitPart=triangle.part;}
  }
  return best-.11f;
}

void HumanoidBase::FitContactLeg(unsigned side,const Vector3 &offset,Quaternion *local,Quaternion *global,Vector3 *positions) const {
  const unsigned hip=side?10:7,knee=hip+1,ankle=hip+2;
  const Vector3 upper=positions[knee]-positions[hip],lower=positions[ankle]-positions[knee];
  const float l1=upper.GetLength(),l2=lower.GetLength();
  const Vector3 direction=(positions[ankle]+offset-positions[hip]).GetNormalized(0);
  const float distance=clamp((positions[ankle]+offset-positions[hip]).GetLength(),std::fabs(l1-l2)+1e-5f,l1+l2-1e-5f);
  const Vector3 target=positions[hip]+direction*distance;
  const Vector3 pole=(upper-direction*upper.GetDotProduct(direction)).GetNormalized(Vector3(0,-1,0));
  const float along=(l1*l1-l2*l2+distance*distance)/(2*distance);
  const Vector3 bend=positions[hip]+direction*along+pole*std::sqrt(std::max(0.0f,l1*l1-along*along));
  const Quaternion thigh=rotationBetween(upper,bend-positions[hip])*global[hip];
  const Quaternion shin=rotationBetween(lower,target-bend)*global[knee];
  const Quaternion shoe=global[ankle];
  local[hip]=(global[0].GetInverse()*thigh).GetNormalized();
  local[knee]=(thigh.GetInverse()*shin).GetNormalized();
  local[ankle]=(shin.GetInverse()*shoe).GetNormalized();
  ContactForwardKinematics(local,global,positions);
}

Vector3 HumanoidBase::GetStandingChestTarget() const {
  if(!chestAnimation)return spatialState.position+spatialState.bodyDirectionVec*.22f+Vector3(0,0,1.4f);
  Animation *animation=chestAnimation.get();float phase=chestContactFrame;bool source=true;
  bool forward=false;
  if(player->GetExternalController()) {
    const Vector3 stick=static_cast<HumanController*>(player->GetExternalController())->GetHIDevice()->GetDirection();
    forward=(match->IsFirstPerson()?stick.coords[1]:stick.GetDotProduct(spatialState.bodyDirectionVec))>.15f;
  }
  for(Animation *candidate:anims->GetAnimations())
    if(candidate->GetVariable("added_chest")=="true" &&
        (candidate->GetVariable("reception_mode")=="forward")==forward) {
      animation=candidate;phase=std::atof(candidate->GetVariable("touchframe").c_str());source=false;break;
    }
  Quaternion local[13],global[13];Vector3 positions[13];
  const float angle=spatialState.angle;
  const Vector3 root=spatialState.position;
  if(!source) {
    SampleContactAnimation(currentAnim->anim,float(currentAnim->frameNum),root,angle,false,local,global,positions);
    BlendUpperReception(animation,phase,1,angle,local);ContactForwardKinematics(local,global,positions);
  } else SampleContactAnimation(animation,phase,root,angle,true,local,global,positions);
  Quaternion facing;facing.SetAngleAxis(angle,Vector3(0,0,1));
  const Vector3 probe=positions[1]+global[1]*Vector3(0,-.4f,.30f)*zMultiplier;
  Vector3 surface;ContactSurface(probe,"chest",global,positions,&surface);
  return surface+(probe-surface).GetNormalized(0)*.111f;
}

void HumanoidBase::AimTrainingHead(Quaternion *local,Quaternion *global,Vector3 *positions,const Vector3 &look) const {
  // Keep the neck within its own anatomical range; the torso is not steered
  // by head look. Skin contacts and rendering use the same orientation.
  const Vector3 bodyLook=global[0].GetInverse()*look.GetNormalized(Vector3(0,-1,0));
  const float yaw=clamp(std::atan2(bodyLook.coords[0],-bodyLook.coords[1]),-1.48f,1.48f);
  const float pitch=clamp(std::atan2(bodyLook.coords[2],bodyLook.Get2D().GetLength()),-1.0f,.85f);
  const Vector3 target=global[0]*Vector3(std::sin(yaw)*std::cos(pitch),-std::cos(yaw)*std::cos(pitch),std::sin(pitch));
  const Quaternion head=rotationBetween(global[2]*Vector3(0,-1,0),target)*global[2];
  local[2]=(global[1].GetInverse()*head).GetNormalized();
  ContactForwardKinematics(local,global,positions);
}

void HumanoidBase::PutTrainingHeadLook() {
  if(!UsesTrainingContacts() || !player->GetExternalController() || fetchedChestPhase>=0)return;
  Quaternion local[13],global[13];Vector3 positions[13];
  for(unsigned i=0;i<13;++i) {
    auto node=nodeMap.at(pes3::nativeBoneNames[i]);local[i]=node->GetRotation();global[i]=node->GetDerivedRotation();
    positions[i]=node->GetDerivedPosition();
  }
  AimTrainingHead(local,global,positions,fetchedTrainingLook);
  nodeMap.at("neck")->SetRotation(local[2],false);
  humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
  if(GetConfiguration()->GetBool("training_telemetry",false)) {
    const Vector3 forward=nodeMap.at("neck")->GetDerivedRotation()*Vector3(0,-1,0);
    const float alignment=forward.GetDotProduct(fetchedTrainingLook.GetNormalized(0));
    printf("TRAINING_HEAD_POSE t=%lu alignment=%.6f yaw=%.5f pitch=%.5f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,
      alignment,std::atan2(forward.coords[1],forward.coords[0]),std::atan2(forward.coords[2],forward.Get2D().GetLength()));
  }
}

void HumanoidBase::ProcessTrainingBodyContact() {
  if(!UsesTrainingContacts())return;
  if(match->GetBallRetainer()) {contactPreviousBallValid=false;return;}
  Ball *ball=match->GetBall();
  const Vector3 current=ball->Predict(0),incoming=ball->GetMovement();
  const bool previousValid=contactPreviousBallValid && (current-contactPreviousBall).GetLength()<1.f;
  const Vector3 previous=previousValid?
    contactPreviousBall:current-incoming*.01f;
  Quaternion priorLocal[13];
  for(unsigned i=0;i<13;++i){priorLocal[i]=previousValid?contactPreviousSkinLocal[i]:contactLocal[i];contactPreviousSkinLocal[i]=contactLocal[i];}
  const Vector3 priorRoot=previousValid?contactPreviousSkinRoot:contactPositions[0];
  contactPreviousSkinRoot=contactPositions[0];
  contactPreviousBall=current;contactPreviousBallValid=true;
  float bodyRange=(current-spatialState.position-Vector3(0,0,1)).GetLength();
  for(auto &position:contactPositions)bodyRange=std::min(bodyRange,(current-position).GetLength());
  auto *actor=static_cast<Player*>(player);
  const bool plannedFootContact=currentAnim->touchFrame>=0 && !currentAnim->touchMade &&
    currentAnim->anim->GetVariable("touch_bodypart").find("foot")!=std::string::npos;
  const bool intentionalGroundControl=!PhysicalRigBusy() && current.coords[2]<.45f && match->GetLastTouchPlayer()==actor &&
    actor->GetLastTouchType()!=e_TouchType_Accidental &&
    (plannedFootContact || actor->HasPossession() || actor->GetLastTouchBias(600)>.01f);
  if(match->GetActualTime_ms()<bodyContactUntil_ms || current.coords[2]<.09f || intentionalGroundControl ||
      bodyRange>1.25f ||
      static_cast<Player*>(player)->GetLastTouchTime_ms()==match->GetActualTime_ms())return;
  Quaternion local[13],global[13];Vector3 positions[13];
  std::copy(contactLocal,contactLocal+13,local);std::copy(contactPositions,contactPositions+13,positions);
  ContactForwardKinematics(local,global,positions);
  auto sampleSkin=[&](float u){
    for(unsigned i=0;i<13;++i)local[i]=priorLocal[i].GetSlerped(u,contactLocal[i]).GetNormalized();
    positions[0]=priorRoot*(1-u)+contactPositions[0]*u;
    ContactForwardKinematics(local,global,positions);
  };
  const float relativeTravel=((current-previous)-(contactPositions[0]-priorRoot)).GetLength();
  const unsigned sweepSamples=std::max(8u,std::min(24u,unsigned(std::ceil(relativeTravel/.035f))));
  Vector3 point,surface;std::string part;float fraction=-1;
  for(unsigned sample=0;sample<=sweepSamples;++sample) {
    const float u=float(sample)/sweepSamples;point=previous*(1-u)+current*u;sampleSkin(u);
    if(ContactSurface(point,"",global,positions,&surface,&part)<=.0005f) {fraction=u;break;}
  }
  if(fraction<0)return;
  float low=std::max(0.0f,fraction-1.f/sweepSamples),high=fraction;
  for(unsigned iteration=0;iteration<16;++iteration) {
    const float u=(low+high)*.5f;
    sampleSkin(u);
    if(ContactSurface(previous*(1-u)+current*u,"",global,positions)>.0005f)low=u;else high=u;
  }
  point=previous*(1-high)+current*high;
  sampleSkin(high);
  ContactSurface(point,"",global,positions,&surface,&part);
  Vector3 normal=(point-surface).GetNormalized(spatialState.bodyDirectionVec);
  // The nearest triangle distance is unsigned. If a moving torso has already
  // enclosed the centre, point-surface points inward; choose the outside of
  // the anatomical segment before resolving the ball.
  Vector3 a=positions[0],b=positions[2];
  if(part=="neck"){a=positions[2]+global[2]*Vector3(0,0,.15f*zMultiplier);b=a;}
  for(unsigned i=3;i<13;++i)if(part==pes3::nativeBoneNames[i]){
    a=positions[i];
    b=(i==3||i==5||i==7||i==8||i==10||i==11)?positions[i+1]:
      a+global[i]*Vector3(0,0,(i==4||i==6?-.30f:-.05f)*zMultiplier);
  }
  const Vector3 axis=b-a;
  const Vector3 centre=a+axis*clamp((surface-a).GetDotProduct(axis)/std::max(.00001f,axis.GetSquaredLength()),0.f,1.f);
  if(normal.GetDotProduct(surface-centre)<0)normal=-normal;
  unsigned struckBone=part=="middle"?1:part=="neck"?2:0;
  for(unsigned i=3;i<13;++i)if(part==pes3::nativeBoneNames[i])struckBone=i;
  const Vector3 localSurface=global[struckBone].GetInverse()*(surface-positions[struckBone]);
  sampleSkin(0);const Vector3 beforeSurface=positions[struckBone]+global[struckBone]*localSurface;
  sampleSkin(1);const Vector3 afterSurface=positions[struckBone]+global[struckBone]*localSurface;
  Vector3 surfaceVelocity=(afterSurface-beforeSurface)*100;
  // Bound the muscular component, not the player's travel. A short pose
  // transition used to turn a torso/arm into an 18 m/s rebounding wall.
  Vector3 localVelocity=surfaceVelocity-spatialState.movement;localVelocity.NormalizeMax(4.f);
  surfaceVelocity=spatialState.movement+localVelocity;
  const Vector3 relative=incoming-surfaceVelocity;
  const float inward=relative.GetDotProduct(normal);
  if(inward>=-.2f)return;
  const bool legalPart=part=="middle"||part=="neck"||part.find("thigh")!=std::string::npos||
    part.find("knee")!=std::string::npos||part.find("ankle")!=std::string::npos;
  const Vector3 toBall=(point-spatialState.position).Get2D().GetNormalized(spatialState.bodyDirectionVec);
  const bool busyStrike=currentAnim->touchFrame>=0&&!currentAnim->touchMade&&
    currentAnim->functionType>=e_FunctionType_ShortPass&&currentAnim->functionType<=e_FunctionType_Shot;
  const bool cushioning=legalPart&&!PhysicalRigBusy()&&!busyStrike&&-inward<18.f&&
    toBall.GetDotProduct(spatialState.bodyDirectionVec)>-.25f&&
    (!match->GetLastTouchPlayer()||match->GetLastTouchPlayer()!=actor||actor->GetLastTouchType()==e_TouchType_Accidental);
  // Only a swept, real skin contact can absorb the pass. A soft receiver
  // withdraws the contacted surface; this is not a proximity possession or
  // an invisible barrier in front of the chest.
  Vector3 outgoing=(relative-normal*inward)*(cushioning?.22f:.65f)-normal*inward*(cushioning?.035f:.18f)+
    (cushioning?spatialState.movement*.70f:surfaceVelocity);
  if(cushioning){
    const float maxLead=std::max(1.3f,spatialState.movement.Get2D().GetLength()+.75f);
    const Vector3 flat=outgoing.Get2D();
    if(flat.GetLength()>maxLead){const Vector3 limited=flat.GetNormalized(0)*maxLead;outgoing.coords[0]=limited.coords[0];outgoing.coords[1]=limited.coords[1];}
    outgoing.coords[2]=clamp(outgoing.coords[2],-2.2f,.8f);
    const float separating=(outgoing-surfaceVelocity).GetDotProduct(normal);
    if(separating<.05f)outgoing+=normal*(.05f-separating);
  }
  const Vector3 resolved=surface+normal*.1105f+outgoing*(1-high)*.01f;
  // A fast ball can cross more than 12 cm in a simulation step. Rejecting
  // that correction allowed it through the torso. Bound it by this sweep.
  if((resolved-current).GetLength()>(current-previous).GetLength()+(afterSurface-beforeSurface).GetLength()+.15f)return;
  ball->ResolveBodyContact(resolved,outgoing);bodyContactUntil_ms=match->GetActualTime_ms()+10;
  contactPreviousBall=resolved;
  auto *contactActor=static_cast<Player*>(player);contactActor->GetTeam()->SetLastTouchPlayer(contactActor,cushioning?e_TouchType_Intentional_Nonkicked:e_TouchType_Accidental);
  contactActor->UpdatePossessionStats(false);ball->TriggerBallTouchSound(.15f);
  if(PhysicalRigEnabled()){
    physicalBallImpactTime=match->GetActualTime_ms();physicalBallImpactVelocity=relative;physicalBallImpactPosition=point;
    physicalBallImpactPart=toBall.GetDotProduct(spatialState.bodyDirectionVec)<-.25f?"back":part;
    const Vector3 impulse=(incoming-outgoing)*.43f;
    AddPhysicalImpulse(impulse,point-contactPositions[0]);
    if(GetConfiguration()->GetBool("training_telemetry",false))printf("PHYSICAL_BALL_REACTION t=%lu actor=%d part=%s speed=%.4f hard=%d impulse=%.4f\n",match->GetActualTime_ms(),player->GetID(),part.c_str(),-inward,-inward>14.f?1:0,impulse.GetLength());
  }
  if(cushioning&&GetConfiguration()->GetBool("training_telemetry",false))
    printf("RECEPTION_CUSHION t=%lu actor=%d part=%s incoming=%.5f outgoing=%.5f skin_gap=%.6f\n",match->GetActualTime_ms(),player->GetID(),part.c_str(),incoming.GetLength(),outgoing.GetLength(),(point-surface).GetLength()-.11f);
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("TRAINING_BODY_TOUCH t=%lu part=%s correction=%.6f sweep=%.5f speed_before=%.5f speed_after=%.5f actor=%d moving_skin=1 samples=%u skin_speed=%.5f\n",
      match->GetActualTime_ms(),part.c_str(),(resolved-current).GetLength(),high,incoming.GetLength(),outgoing.GetLength(),player->GetID(),sweepSamples,surfaceVelocity.GetLength());
}

void HumanoidBase::PlanHeelPreparation() {
  const bool heel=currentAnim->anim->GetVariable("physical_heel")=="true";
  const bool kick=currentAnim->functionType==e_FunctionType_ShortPass||currentAnim->functionType==e_FunctionType_LongPass||
    currentAnim->functionType==e_FunctionType_HighPass||currentAnim->functionType==e_FunctionType_Shot;
  const bool stationary=kick&&currentAnim->anim->GetVariable("touch_bodypart").find("foot")!=std::string::npos&&
    match->GetBall()->Predict(0).coords[2]<.22f&&match->GetBall()->GetMovement().GetLength()<2.f;
  if(!PhysicalRigEnabled() || (!heel&&!stationary) ||
      currentAnim->touchFrame<20 || currentAnim->positions.empty())return;
  const int end=currentAnim->touchFrame;
  const float count=end+1.f;
  std::vector<Vector3> approach(end+1);Vector3 sum(0);
  for(int frame=0;frame<=end;++frame){
    sum+=currentAnim->actionSmuggle*(football_contact::approachWeight(frame,unsigned(count))/count);
    approach[frame]=sum;
  }
  auto envelope=[&](int frame){const float s=std::sin(pi*float(frame)/end);return s*s;};
  auto clearance=[&](const Vector3 &offset){
    float least=100;Quaternion local[13],global[13];Vector3 positions[13];
    for(int frame=2;frame<end-3;frame+=2){
      const Vector3 root=spatialState.position+currentAnim->positions[frame]+approach[frame]+offset*envelope(frame);
      const float begin=std::min(1.f,(frame+1.f)/16.f);
      const float yaw=spatialState.angle+currentAnim->rotationSmuggle.begin*(1-begin);
      SampleContactAnimation(currentAnim->anim,frame,root,yaw,false,local,global,positions);
      const Vector3 ball=match->GetBall()->Predict(frame*10);
      least=std::min(least,std::min(ContactSurface(ball,"left_foot",global,positions),ContactSurface(ball,"right_foot",global,positions)));
    }
    return least;
  };
  const float before=clearance(Vector3(0));if(before>=.006f)return;
  const Vector3 front=spatialState.bodyDirectionVec.Get2D().GetNormalized(Vector3(1,0,0));
  const Vector3 side=front.GetRotated2D(.5f*pi);
  Vector3 chosen(0);float after=before;
  for(float amplitude:{.04f,.08f,.12f,.16f,.20f,.24f}){
    for(const Vector3 direction:{side,-side,-front,front}){
      const Vector3 offset=direction*amplitude;const float gap=clearance(offset);
      if(gap>after){after=gap;chosen=offset;}
    }
    if(after>=.006f)break;
  }
  // A bounded whole-player support step avoids kicking the ball during
  // preparation. Both endpoints and the authored ball contact stay fixed;
  // feet are never warped independently and no collision is suppressed.
  for(int frame=1;frame<end;++frame)currentAnim->positions[frame]+=chosen*envelope(frame);
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("TRAINING_HEEL_CLEARANCE t=%lu before=%.6f after=%.6f offset=%.6f\n",match->GetActualTime_ms(),before,after,chosen.GetLength());
  if(!heel&&GetConfiguration()->GetBool("training_telemetry",false))
    printf("TRAINING_KICK_CLEARANCE t=%lu before=%.6f after=%.6f offset=%.6f\n",match->GetActualTime_ms(),before,after,chosen.GetLength());
}

void HumanoidBase::UpdateTrainingContactPose() {
  contactPoseBlend=0;
  if(!UsesTrainingContacts() && !PhysicalRigEnabled())return;
  const unsigned frame=std::min<unsigned>(currentAnim->frameNum,currentAnim->positions.size()-1);
  Vector3 approach=currentAnim->actionSmuggleOffset;
  if(currentAnim->touchFrame>0 && currentAnim->frameNum<=currentAnim->touchFrame) {
    const float n=float(currentAnim->touchFrame+1);
    const float weight=1-.1f*std::cos(2*pi*currentAnim->frameNum/n);
    approach+=currentAnim->actionSmuggle*(weight/n);
  }
  Vector3 movement=currentAnim->movementSmuggleOffset;
  if(currentAnim->touchFrame<0 && currentAnim->frameNum<=currentAnim->anim->GetEffectiveFrameCount()) {
    const float n=float(currentAnim->anim->GetEffectiveFrameCount()+1);
    movement+=currentAnim->movementSmuggle*((1-.1f*std::cos(2*pi*currentAnim->frameNum/n))/n);
  }
  const Vector3 root=startPos+currentAnim->positions[frame]+approach+
    currentAnim->actionSmuggleSustainOffset+movement;
  const float begin=std::min(1.0f,(currentAnim->frameNum+1.0f)/
    std::min(16.0f,currentAnim->touchFrame>=0?currentAnim->touchFrame+1.0f:currentAnim->anim->GetEffectiveFrameCount()+1.0f));
  const float end=currentAnim->touchFrame<0?begin:currentAnim->frameNum>currentAnim->touchFrame?
    float(currentAnim->frameNum-currentAnim->touchFrame)/(currentAnim->anim->GetEffectiveFrameCount()-currentAnim->touchFrame):0;
  const float angle=startAngle+currentAnim->rotationSmuggle.begin*(1-begin)+currentAnim->rotationSmuggle.end*end;
  SampleContactAnimation(currentAnim->anim,float(currentAnim->frameNum),root,angle,
    false,contactLocal,contactGlobal,contactPositions);
  UpdatePhysicalRigPose();
  if(match->GetReferee()->KeepThrowerOutside(player)){
    const float side=match->GetRefereeBuffer().restartPos.coords[1]>=0?1.f:-1.f;
    float margin=100;
    for(unsigned foot:{9u,12u}){
      Vector3 surface;ContactSurface(contactPositions[foot]+Vector3(0,-side*2.f,0),foot==9?"left_foot":"right_foot",contactGlobal,contactPositions,&surface);
      margin=std::min(margin,side*surface.coords[1]-pitchHalfH);
    }
    if(margin<.025f){
      const Vector3 correction(0,side*(.025f-margin),0);
      OffsetPosition(correction);for(auto &position:contactPositions)position+=correction;
    }
    if(GetConfiguration()->GetBool("training_telemetry",false)&&match->GetActualTime_ms()%50==0)
      printf("RESTART_FOOTING t=%lu actor=%d margin=%.6f correction=%.6f\n",match->GetActualTime_ms(),player->GetID(),std::max(.025f,margin),std::max(0.f,.025f-margin));
  }
  if(!UsesTrainingContacts())return;
  const int remaining=currentAnim->touchFrame-currentAnim->frameNum;
  const float nativeBlend=currentAnim->touchFrame>=0 ?
      ease((20-remaining)/10.0f)*ease((remaining+14)/9.0f) : 0;
  if(PhysicalRigEnabled()){
    const float enter=football_physics::smooth(currentAnim->frameNum/std::max(1.f,std::min(8.f,currentAnim->touchFrame*.5f)));
    contactPoseBlend=nativeBlend*enter;
    if(physicalWalkWeight>.001f)contactPoseBlend=1.f;
    if(physicalRig&&physicalRig->initialized())contactPoseBlend=std::max(contactPoseBlend,physicalRig->metrics().recoveryStep);
  }
  if(GetConfiguration()->GetBool("training_telemetry",false) && currentAnim->touchFrame>=0 && match->GetActualTime_ms()%20==0) {
    const Vector3 point=match->GetBall()->Predict(0),next=match->GetBall()->Predict(10);
    printf("TRAINING_NATIVE_GEOMETRY t=%lu frame=%d contact_frame=%d left=%.5f right=%.5f next_left=%.5f next_right=%.5f touched=%d\n",
      match->GetActualTime_ms(),currentAnim->frameNum,currentAnim->touchFrame,
      ContactSurface(point,"left_foot",contactGlobal,contactPositions),ContactSurface(point,"right_foot",contactGlobal,contactPositions),
      ContactSurface(next,"left_foot",contactGlobal,contactPositions),ContactSurface(next,"right_foot",contactGlobal,contactPositions),currentAnim->touchMade?1:0);
  }

  if(currentAnim->touchFrame<0) {

    return;
  }
  if(remaining>20 || remaining< -14)return;
  if(!PhysicalRigEnabled())contactPoseBlend=0;
  // Authored joint rotations stay intact. Contact is planned with the
  // native whole-player approach, never a late per-leg reach adjustment.

}

void HumanoidBase::PutTrainingContactPose() {
  if(!UsesTrainingContacts() || fetchedContactBlend<=0)return;
  const float amount=fetchedContactBlend;
  // A native touch must remain visible while the previous dribble fades out.
  // Remove its visual support lift before applying the physical contact pose.
  auto body=nodeMap.at("body");const auto &bind=pes3NativeReference.offsets[0];
  body->SetPosition(body->GetPosition()*(1-amount)+Vector3(bind[0],bind[1],bind[2])*amount,false);
  Vector3 root=humanoidNode->GetPosition();
  root=root*(1-amount)+(fetchedContactRoot+Vector3(0,0,fetchedContactHeight/zMultiplier-.96f))*amount;
  humanoidNode->SetPosition(root,false);
  for(unsigned i=0;i<13;++i) {
    auto node=nodeMap.at(pes3::nativeBoneNames[i]);
    node->SetRotation(node->GetRotation().GetSlerped(amount,fetchedContactLocal[i]).GetNormalized(),false);
  }
  humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
  Quaternion local[13],global[13];Vector3 positions[13];
  const Vector3 origin=humanoidNode->GetPosition().Get2D();
  for(unsigned i=0;i<13;++i) {
    const auto node=nodeMap.at(pes3::nativeBoneNames[i]);
    local[i]=node->GetRotation();global[i]=node->GetDerivedRotation();
    positions[i]=origin+(node->GetDerivedPosition()-origin)*zMultiplier;
  }
  const Vector3 sphere=match->GetBall()->GetBallGeom()->GetPosition();
  const float renderedFootShift=0;
  humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
  if(GetConfiguration()->GetBool("training_telemetry",false)) {
    for(unsigned i=0;i<13;++i) {
      const auto node=nodeMap.at(pes3::nativeBoneNames[i]);global[i]=node->GetDerivedRotation();
      positions[i]=origin+(node->GetDerivedPosition()-origin)*zMultiplier;
    }
    const std::string part=fetchedChestPhase>=0?"chest":fetchedbuf_animApplyBuffer.anim->GetVariable("touch_bodypart");
    const float gap=ContactSurface(sphere,part,global,positions);
    float lengthError=0;
    for(unsigned i=1;i<13;++i) {
      const auto &offset=pes3NativeReference.offsets[i];
      const float expected=Vector3(offset[0],offset[1],offset[2]).GetLength()*zMultiplier;
      lengthError=std::max(lengthError,std::fabs((positions[i]-positions[pes3::nativeParents[i]]).GetLength()-expected));
    }
    if(fetchedChestPhase>=0)
      printf("TRAINING_CHEST_POSE t=%lu phase=%.3f blend=%.4f gap=%.5f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,fetchedChestPhase,amount,gap);
    else
      printf("TRAINING_NATIVE_POSE t=%lu blend=%.4f dribble_remaining=%.4f gap=%.5f gap_left=%.5f gap_right=%.5f foot_shift=%.5f length_error=%.6f\n",
        fetchedbuf_animApplyBuffer.snapshotTime_ms,amount,fetchedbuf_animApplyBuffer.dribbleTrialBlend,gap,
        ContactSurface(sphere,"left_ankle",global,positions),ContactSurface(sphere,"right_ankle",global,positions),renderedFootShift,lengthError);
  }
}
