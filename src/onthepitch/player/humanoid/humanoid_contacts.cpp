// Contacts on the same weighted skin and native skeleton used for rendering.
#include "humanoidbase.hpp"
#include "../../match.hpp"
#include "../player.hpp"
#include "../../../main.hpp"
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

void HumanoidBase::CaptureContactMesh() {
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
    if(!source) {
      const auto offset=offsets.find(pes3::nativeBoneNames[i]);
      if(offset!=offsets.end()) {
        const auto &v=offset->second;
        local[i]=local[i].GetSlerped(v.bias,v.isRelative?v.orientation*local[i]:v.orientation).GetNormalized();
      }
    }
    if(i==0){Quaternion turn;turn.SetAngleAxis(facing,Vector3(0,0,1));local[i]=turn*local[i];}
  }
  ContactForwardKinematics(local,global,positions);
}

float HumanoidBase::ContactSurface(const Vector3 &point,const std::string &requested,const Quaternion *global,
    const Vector3 *positions,Vector3 *closest) const {
  const std::string part=skinPart(requested);
  float best=100;
  for(const auto &triangle:contactTriangles) {
    if(!part.empty() && triangle.part!=(part=="chest"?"middle":part))continue;
    if(part=="chest") {
      float bindHeight=0;
      for(unsigned c=0;c<3;++c)bindHeight+=uniqueFullbodyMesh[triangle.mesh].data[triangle.vertices[c]*3+2]/(3*zMultiplier);
      if(bindHeight<1.23f || bindHeight>1.52f)continue;
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
    if(d<best){best=d;if(closest)*closest=surface;}
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
  Quaternion local[13],global[13];Vector3 positions[13];
  const float angle=spatialState.angle;
  SampleContactAnimation(chestAnimation.get(),chestContactFrame,spatialState.position,angle,true,local,global,positions);
  Quaternion facing;facing.SetAngleAxis(angle,Vector3(0,0,1));
  const Vector3 probe=positions[1]+global[1]*Vector3(0,-.4f,.30f)*zMultiplier;
  Vector3 surface;ContactSurface(probe,"chest",global,positions,&surface);
  return surface+(probe-surface).GetNormalized(0)*.111f;
}

void HumanoidBase::UpdateChestReception() {
  if(!TrainingEnabled() || !chestAnimation || match->GetDesignatedPossessionPlayer()!=player)return;
  auto *human=static_cast<HumanController*>(player->GetExternalController());
  if(!human)return;
  if(chestActive) {
    if(human->GetFloatVelocity()>.8f || human->GetActionMode()!=0 || chestPhase>=chestAnimation->GetEffectiveFrameCount()) {
      chestActive=false;chestCooldown_ms=match->GetActualTime_ms()+500;
      float lo=0,hi=1;
      for(unsigned i=0;i<20;++i){const float u=(lo+hi)*.5f;if(ease(u)<contactPoseBlend)lo=u;else hi=u;}
      const unsigned elapsed=unsigned((1-hi)*180);
      chestStarted_ms=match->GetActualTime_ms()>elapsed?match->GetActualTime_ms()-elapsed:0;
    }
    return;
  }
  if(match->GetActualTime_ms()<chestCooldown_ms || human->GetFloatVelocity()>.8f ||
      human->GetActionMode()!=0 || spatialState.actualMovement.GetLength()>.8f)return;
  const Vector3 target=GetStandingChestTarget(),incoming=match->GetBall()->GetMovement();
  const Vector3 delta=match->GetBall()->Predict(0)-target;
  if(delta.Get2D().GetLength()>6 || incoming.Get2D().GetLength()<2 || delta.GetDotProduct(incoming)>=0)return;
  Quaternion facing;facing.SetAngleAxis(spatialState.angle,Vector3(0,0,1));
  if(delta.Get2D().GetNormalized(0).GetDotProduct(facing*Vector3(0,-1,0))<.7f)return;
  unsigned bestTime=0;float best=100;
  for(unsigned ms=100;ms<=700;ms+=10) {
    const float distance=(match->GetBall()->Predict(ms)-target).GetLength();
    if(distance<best){best=distance;bestTime=ms;}
  }
  // Play the presentation from its first pose. Late arrivals retain a native reception.
  if(best>.16f || bestTime<unsigned(std::ceil(chestContactFrame*10)))return;
  chestActive=true;chestTouched=false;chestPhase=chestContactFrame-bestTime*.1f;
  chestRoot=spatialState.position;chestAngle=spatialState.angle;chestFacing=facing;
  chestPreviousBall=match->GetBall()->Predict(0);chestStarted_ms=match->GetActualTime_ms();
  dribbleLoopRequested=false;dribbleLoopOwnsBall=false;
  printf("TRAINING_CHEST_START t=%lu arrival_ms=%u phase=%.3f target=[%.4f,%.4f,%.4f]\n",
      match->GetActualTime_ms(),bestTime,chestPhase,target.coords[0],target.coords[1],target.coords[2]);
}

void HumanoidBase::ProcessChestReception() {
  if(!chestActive)return;
  chestPhase+=1;
  const float phase=clamp(chestPhase,0.0f,float(chestAnimation->GetEffectiveFrameCount()));
  const float enter=ease(phase/18),exit=ease((chestAnimation->GetEffectiveFrameCount()-phase)/22);
  contactPoseBlend=enter*exit;
  SampleContactAnimation(chestAnimation.get(),phase,chestRoot,chestAngle,true,contactLocal,contactGlobal,contactPositions);
  Ball *ball=match->GetBall();ball->CalculatePrediction();
  const Vector3 current=ball->Predict(0);Vector3 surface;
  float gap=ContactSurface(current,"chest",contactGlobal,contactPositions,&surface);
  // A real sphere/skin crossing, not an authored marker's 40 cm acceptance radius.
  if(!chestTouched && contactPoseBlend>.999f && gap<=.001f && gap>-.11f &&
      current.coords[2]>1.0f && current.coords[2]<1.85f && std::fabs(phase-chestContactFrame)<18) {
    const float penetration=gap;
    Vector3 collisionPoint=current;float sweep=1;
    if(ContactSurface(chestPreviousBall,"chest",contactGlobal,contactPositions)>.0005f) {
      float lo=0,hi=1;
      for(unsigned i=0;i<20;++i) {
        const float fraction=(lo+hi)*.5f;
        const Vector3 point=chestPreviousBall*(1-fraction)+current*fraction;
        if(ContactSurface(point,"chest",contactGlobal,contactPositions)>.0005f)lo=fraction;else hi=fraction;
      }
      sweep=hi;collisionPoint=chestPreviousBall*(1-sweep)+current*sweep;
      gap=ContactSurface(collisionPoint,"chest",contactGlobal,contactPositions,&surface);
    }
    const Vector3 normal=(collisionPoint-surface).GetNormalized(chestFacing*Vector3(0,-1,0));
    const Vector3 incoming=ball->GetMovement();
    const float inward=incoming.GetDotProduct(normal);
    if(inward<-.2f && normal.GetDotProduct(chestFacing*Vector3(0,-1,0))>.3f) {
      const Vector3 tangent=incoming-normal*inward;
      Vector3 outgoing=normal*clamp(-inward*.10f,.35f,1.1f)+tangent*.12f;
      outgoing.coords[2]=clamp(outgoing.coords[2],-1.2f,-.45f);
      // Only undo this 10 ms penetration. Preserve spin/history and never pull a remote ball.
      const Vector3 resolved=surface+normal*.1105f+outgoing*(1-sweep)*.01f;
      ball->ResolveBodyContact(resolved,outgoing);
      auto *p=static_cast<Player*>(player);
      p->GetTeam()->SetLastTouchPlayer(p,e_TouchType_Intentional_Nonkicked);
      p->UpdatePossessionStats(false);ball->TriggerBallTouchSound(.18f);
      chestTouched=true;
      printf("TRAINING_CHEST_TOUCH t=%lu phase=%.4f gap=%.5f correction=%.5f step_penetration=%.5f sweep=%.5f speed_before=%.4f speed_after=%.4f ball=[%.4f,%.4f,%.4f]\n",
        match->GetActualTime_ms(),phase,gap,(resolved-current).GetLength(),penetration,sweep,incoming.GetLength(),outgoing.GetLength(),resolved.coords[0],resolved.coords[1],resolved.coords[2]);
    }
  }
  chestPreviousBall=current;
  if(GetConfiguration()->GetBool("training_telemetry",false) && match->GetActualTime_ms()%20==0)
    printf("TRAINING_CHEST_STATE t=%lu phase=%.3f blend=%.4f gap=%.5f touched=%d\n",match->GetActualTime_ms(),phase,contactPoseBlend,gap,chestTouched?1:0);
}

void HumanoidBase::UpdateTrainingContactPose() {
  contactPoseBlend=0;
  if(!TrainingEnabled())return;
  const unsigned frame=std::min<unsigned>(currentAnim->frameNum,currentAnim->positions.size()-1);
  const Vector3 root=startPos+currentAnim->positions[frame]+currentAnim->actionSmuggleOffset+
    currentAnim->actionSmuggleSustainOffset+currentAnim->movementSmuggleOffset;
  SampleContactAnimation(currentAnim->anim,currentAnim->frameNum+.5f,root,startAngle+currentAnim->rotationSmuggleOffset,
    false,contactLocal,contactGlobal,contactPositions);
  if(!chestActive && chestAnimation && chestPhase>0 && chestPhase<chestAnimation->GetEffectiveFrameCount() &&
      match->GetActualTime_ms()<chestStarted_ms+180 && chestCooldown_ms>match->GetActualTime_ms()) {
    chestPhase=std::min(chestPhase+1,float(chestAnimation->GetEffectiveFrameCount()));
    contactPoseBlend=ease(1-float(match->GetActualTime_ms()-chestStarted_ms)/180);
    SampleContactAnimation(chestAnimation.get(),chestPhase,root,chestAngle,true,contactLocal,contactGlobal,contactPositions);
    return;
  }
  if(chestActive || dribbleLoopRequested || currentAnim->touchFrame<0)return;
  const int remaining=currentAnim->touchFrame-currentAnim->frameNum;
  if(remaining>20 || remaining< -14)return;
  contactPoseBlend=ease((20-remaining)/10.0f)*ease((remaining+14)/14.0f);
  const std::string part=skinPart(currentAnim->anim->GetVariable("touch_bodypart"));
  const int side=part=="left_ankle"?0:part=="right_ankle"?1:-1;
  if(side<0)return;
  // Reach with the existing leg, preserving segment lengths. The ball keeps its physical path.
  const Vector3 point=match->GetBall()->Predict(std::max(0,remaining)*10);
  for(unsigned iteration=0;iteration<4;++iteration) {
    Vector3 surface;const float gap=ContactSurface(point,part,contactGlobal,contactPositions,&surface);
    if(std::fabs(gap-.0005f)<.0003f || gap>(currentAnim->functionType==e_FunctionType_BallControl?.22f:.35f))break;
    Vector3 offset;
    if(gap<0) {
      const unsigned ankle=side?12:9;
      const auto &lo=pes3NativeReference.footMin[side],&hi=pes3NativeReference.footMax[side];
      const Vector3 center=contactPositions[ankle]+contactGlobal[ankle]*Vector3((lo[0]+hi[0])*.5f,(lo[1]+hi[1])*.5f,(lo[2]+hi[2])*.5f)*zMultiplier;
      offset=(center-point).GetNormalized(0)*std::min(.075f,.0005f-gap);
    } else offset=(point-surface).GetNormalized(0)*std::min(.075f,gap-.0005f);
    offset*=contactPoseBlend;
    FitContactLeg(side,offset,contactLocal,contactGlobal,contactPositions);
  }
  // At full leg extension a small weight shift reaches the ball naturally.
  // Keep this in the buffered pose, never move a distant ball to a marker.
  Vector3 surface;const float residual=ContactSurface(point,part,contactGlobal,contactPositions,&surface);
  if(residual>.002f && residual<.025f) {
    const Vector3 direction=(point-surface).Get2D().GetNormalized(0);
    float lo=0,hi=.025f;
    Vector3 trial[13];
    for(unsigned iteration=0;iteration<20;++iteration) {
      const float amount=(lo+hi)*.5f;
      for(unsigned i=0;i<13;++i)trial[i]=contactPositions[i]+direction*amount;
      if(ContactSurface(point,part,contactGlobal,trial)>.0005f)lo=amount;else hi=amount;
    }
    for(unsigned i=0;i<13;++i)trial[i]=contactPositions[i]+direction*hi;
    if(std::fabs(ContactSurface(point,part,contactGlobal,trial)-.0005f)<.0005f)
      for(unsigned i=0;i<13;++i)contactPositions[i]=trial[i];
  }
}

bool HumanoidBase::CanMakeTrainingContact(const std::string &part) {
  if(!TrainingEnabled())return true;
  Vector3 surface;float gap=ContactSurface(match->GetBall()->Predict(0),part,contactGlobal,contactPositions,&surface);
  const float originalGap=gap;
  bool accepted=gap<=.002f && gap>=-.11f;
  if(accepted && gap<0) {
    Ball *ball=match->GetBall();
    const Vector3 initial=ball->Predict(0);Vector3 anchor=surface;
    const std::string skin=skinPart(part);
    const int side=skin=="left_ankle"?0:skin=="right_ankle"?1:-1;
    if(side>=0) {
      const unsigned ankle=side?12:9;
      const auto &lo=pes3NativeReference.footMin[side],&hi=pes3NativeReference.footMax[side];
      anchor=contactPositions[ankle]+contactGlobal[ankle]*Vector3((lo[0]+hi[0])*.5f,(lo[1]+hi[1])*.5f,(lo[2]+hi[2])*.5f)*zMultiplier;
    } else if(skin=="neck")anchor=contactPositions[2]+contactGlobal[2]*Vector3(0,-.01f,.09f)*zMultiplier;
    const Vector3 normal=(initial-anchor).GetNormalized(spatialState.bodyDirectionVec);
    float lo=0,hi=.22f;
    for(unsigned i=0;i<20;++i) {
      const float amount=(lo+hi)*.5f;
      if(ContactSurface(initial+normal*amount,part,contactGlobal,contactPositions)<.0005f)lo=amount;else hi=amount;
    }
    gap=ContactSurface(initial+normal*hi,part,contactGlobal,contactPositions);
    if(std::fabs(gap-.0005f)<.0005f)ball->ResolveBodyContact(initial+normal*hi,ball->GetMovement());
    else accepted=false;
  }
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("TRAINING_NATIVE_SURFACE t=%lu part=%s function=%d gap=%.5f before=%.5f accepted=%d\n",match->GetActualTime_ms(),
      part.c_str(),int(currentAnim->functionType),gap,originalGap,accepted?1:0);
  return accepted;
}

void HumanoidBase::PutTrainingContactPose() {
  if(!TrainingEnabled() || fetchedContactBlend<=0 || fetchedbuf_animApplyBuffer.dribbleTrialBlend>.01f)return;
  const float amount=fetchedContactBlend;
  Vector3 root=humanoidNode->GetPosition();
  root=root*(1-amount)+(fetchedContactRoot+Vector3(0,0,fetchedContactHeight/zMultiplier-.96f))*amount;
  humanoidNode->SetPosition(root,false);
  for(unsigned i=0;i<13;++i) {
    auto node=nodeMap.at(pes3::nativeBoneNames[i]);
    node->SetRotation(node->GetRotation().GetSlerped(amount,fetchedContactLocal[i]).GetNormalized(),false);
  }
  humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
  if(fetchedChestPhase>=0 && GetConfiguration()->GetBool("training_telemetry",false)) {
    Quaternion global[13];Vector3 positions[13];
    const Vector3 origin=humanoidNode->GetPosition().Get2D();
    for(unsigned i=0;i<13;++i) {
      const auto node=nodeMap.at(pes3::nativeBoneNames[i]);global[i]=node->GetDerivedRotation();
      positions[i]=origin+(node->GetDerivedPosition()-origin)*zMultiplier;
    }
    const float gap=ContactSurface(match->GetBall()->GetBallGeom()->GetPosition(),"chest",global,positions);
    printf("TRAINING_CHEST_POSE t=%lu phase=%.3f blend=%.4f gap=%.5f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,fetchedChestPhase,amount,gap);
  }
}
