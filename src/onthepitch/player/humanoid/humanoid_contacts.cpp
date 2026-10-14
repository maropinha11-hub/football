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
    if(!source && animation->GetAnimType()=="movement") {
      const auto offset=offsets.find(pes3::nativeBoneNames[i]);
      if(offset!=offsets.end()) {
        const auto &v=offset->second;
        local[i]=local[i].GetSlerped(v.bias,v.isRelative?v.orientation*local[i]:v.orientation).GetNormalized();
      }
    }
    if(i==0){Quaternion turn;turn.SetAngleAxis(facing,Vector3(0,0,1));local[i]=turn*local[i];}
  }
  ContactForwardKinematics(local,global,positions);
  if(TrainingEnabled() && player->GetExternalController()) {
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
  Quaternion local[13],global[13];Vector3 positions[13];
  const float angle=chestActive?chestAngle:spatialState.angle;
  const Vector3 root=chestActive?chestRoot:spatialState.position;
  SampleContactAnimation(chestAnimation.get(),chestContactFrame,root,angle,true,local,global,positions);
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
    const unsigned long now=match->GetActualTime_ms();
    const bool moving=human->GetFloatVelocity()>.05f;
    const unsigned arrival=unsigned(std::max(0.0f,(chestContactFrame-chestPhase)*10));
    const bool missed=!chestTouched &&
        (match->GetBall()->Predict(arrival)-GetStandingChestTarget()).GetLength()>.20f;
    const bool canExit=chestTouched && now>=chestSettleUntil_ms &&
        (match->GetBall()->Predict(0).coords[2]<.45f || chestPhase>=chestContactFrame+40);
    const bool finished=chestPhase>=chestAnimation->GetEffectiveFrameCount() && chestFinish_ms && now>=chestFinish_ms;
    if((moving && (!chestTouched || canExit)) || (human->GetActionMode()!=0 && (!chestTouched || canExit)) || missed || finished) {
      if(!chestTouched) {
        // Return immediately to the original moving reception selector.
        interruptAnim=e_InterruptAnim_ReQueue;
        if(GetConfiguration()->GetBool("training_telemetry",false))
          printf("TRAINING_CHEST_CANCEL t=%lu moving=%d phase=%.4f\n",now,moving?1:0,chestPhase);
      }
      chestActive=false;chestCooldown_ms=match->GetActualTime_ms()+500;
      float lo=0,hi=1;
      for(unsigned i=0;i<20;++i){const float u=(lo+hi)*.5f;if(ease(u)<contactPoseBlend)lo=u;else hi=u;}
      const unsigned elapsed=unsigned((1-hi)*180);
      chestStarted_ms=match->GetActualTime_ms()>elapsed?match->GetActualTime_ms()-elapsed:0;
    }
    return;
  }
  if(match->GetActualTime_ms()<chestCooldown_ms || human->GetFloatVelocity()>.05f ||
      human->GetActionMode()!=0 || spatialState.actualMovement.GetLength()>.8f)return;
  const Vector3 target=GetStandingChestTarget(),incoming=match->GetBall()->GetMovement();
  const Vector3 delta=match->GetBall()->Predict(0)-target;
  if(delta.Get2D().GetLength()>6 || incoming.GetLength()<.5f || delta.GetDotProduct(incoming)>=0)return;
  Quaternion facing;facing.SetAngleAxis(spatialState.angle,Vector3(0,0,1));
  if(delta.Get2D().GetLength()>.2f && delta.Get2D().GetNormalized(0).GetDotProduct(facing*Vector3(0,-1,0))<.7f)return;
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
  chestRecoveryBase=Vector3(0);chestAppliedMotion=Vector3(0);
  chestSettleUntil_ms=0;chestFinish_ms=0;
  dribbleLoopRequested=false;dribbleLoopOwnsBall=false;
  printf("TRAINING_CHEST_START t=%lu arrival_ms=%u phase=%.3f target=[%.4f,%.4f,%.4f]\n",
      match->GetActualTime_ms(),bestTime,chestPhase,target.coords[0],target.coords[1],target.coords[2]);
}

void HumanoidBase::ProcessChestReception() {
  if(!chestActive)return;
  const float end=float(chestAnimation->GetEffectiveFrameCount());
  if(!chestTouched || match->GetActualTime_ms()>=chestSettleUntil_ms)
    chestPhase=std::min(chestPhase+(chestTouched?.85f:1.0f),end);
  if(chestPhase>=end && !chestFinish_ms)chestFinish_ms=match->GetActualTime_ms()+120;
  const float phase=clamp(chestPhase,0.0f,float(chestAnimation->GetEffectiveFrameCount()));
  Vector3 displacement;
  if(chestTouched) {
    const Vector3 recovery=chestFacing*(ChestRootMotion(phase)-chestRecoveryBase)*zMultiplier;
    displacement=recovery-chestAppliedMotion;chestAppliedMotion=recovery;
  }
  const Vector3 desiredRoot=chestRoot+displacement;
  // The idle native graph can requeue while the presentation owns movement.
  // Anchor that graph to the actual authored root, so a requeue cannot undo
  // the recovery's displacement or leave the visible body walking in place.
  const Vector3 correction=desiredRoot-animApplyBuffer.position.Get2D();
  if(correction.GetLength()>.000001f)OffsetPosition(correction);
  animApplyBuffer.position+=correction;spatialState.position=desiredRoot;chestRoot=desiredRoot;
  contactPoseBlend=ease(phase/18);
  SampleContactAnimation(chestAnimation.get(),phase,chestRoot,chestAngle,true,contactLocal,contactGlobal,contactPositions);
  Ball *ball=match->GetBall();ball->CalculatePrediction();
  const Vector3 current=ball->Predict(0);Vector3 surface;
  float gap=ContactSurface(current,"chest",contactGlobal,contactPositions,&surface);
  // Sweep the complete physics step, including fast and descending balls
  // that have already left the shirt surface at its endpoint.
  if(!chestTouched && contactPoseBlend>.999f && std::fabs(phase-chestContactFrame)<18) {
    const float penetration=gap;
    Vector3 collisionPoint=current;float sweep=-1;
    float lo=0,hi=0;
    for(unsigned sample=0;sample<=12;++sample) {
      const float fraction=sample/12.0f;
      const Vector3 point=chestPreviousBall*(1-fraction)+current*fraction;
      if(ContactSurface(point,"chest",contactGlobal,contactPositions)<=.0005f) {hi=fraction;sweep=fraction;break;}
      lo=fraction;
    }
    if(sweep>=0) {
      for(unsigned i=0;i<20;++i) {
        const float fraction=(lo+hi)*.5f;
        const Vector3 point=chestPreviousBall*(1-fraction)+current*fraction;
        if(ContactSurface(point,"chest",contactGlobal,contactPositions)>.0005f)lo=fraction;else hi=fraction;
      }
      sweep=hi;collisionPoint=chestPreviousBall*(1-sweep)+current*sweep;
      gap=ContactSurface(collisionPoint,"chest",contactGlobal,contactPositions,&surface);
      const Vector3 normal=(collisionPoint-surface).GetNormalized(chestFacing*Vector3(0,-1,0));
      const Vector3 incoming=ball->GetMovement();
      const float inward=incoming.GetDotProduct(normal);
      if(inward<-.2f && collisionPoint.coords[2]>1.0f && collisionPoint.coords[2]<GetStandingChestTarget().coords[2]+.11f && normal.GetDotProduct(chestFacing*Vector3(0,-1,0))>.3f) {
        const Vector3 forward=chestFacing*Vector3(0,-1,0);
        Vector3 outgoing=forward*clamp(-inward*.18f,1.1f,2.2f);
        outgoing.coords[2]=clamp(incoming.coords[2]*.12f,-1.2f,-.45f);
        // Separate only the actual 10 ms skin crossing. Plan the cushioned
        // outgoing velocity with the same bounce/drag prediction as the ball.
        const Vector3 resolved=surface+normal*.1105f+outgoing*(1-sweep)*.01f;
        ball->ResolveBodyContact(resolved,outgoing);
        const Vector3 remainingSteps=chestFacing*(ChestRootMotion(end)-ChestRootMotion(phase))*zMultiplier;
        const Vector3 target=chestRoot+remainingSteps+forward*.46f;
        const unsigned recovery_ms=unsigned(std::ceil((end-phase)*10/.85f))+240;
        for(unsigned iteration=0;iteration<8;++iteration) {
          ball->SetMomentum(outgoing);
          const Vector3 error=(target-ball->Predict(recovery_ms)).Get2D();
          if(error.GetLength()<.005f)break;
          const Vector3 candidate=outgoing+error/(recovery_ms*.001f)*.8f;
          if(!std::isfinite(candidate.GetLength()) || candidate.Get2D().GetLength()>3.5f || candidate.GetDotProduct(normal)<.15f)break;
          outgoing=candidate;
        }
        // Apply one impulse at the chest, never a later invisible correction.
        outgoing.coords[2]=clamp(incoming.coords[2]*.12f,-1.2f,-.45f);
        ball->SetMomentum(outgoing);
        chestSettleUntil_ms=match->GetActualTime_ms()+120;
        auto *p=static_cast<Player*>(player);
        p->GetTeam()->SetLastTouchPlayer(p,e_TouchType_Intentional_Nonkicked);
        p->UpdatePossessionStats(false);ball->TriggerBallTouchSound(.18f);
        chestTouched=true;
        chestRecoveryBase=ChestRootMotion(phase);chestAppliedMotion=Vector3(0);
        printf("TRAINING_CHEST_TOUCH t=%lu phase=%.4f gap=%.5f correction=%.5f step_penetration=%.5f sweep=%.5f speed_before=%.4f speed_after=%.4f ball=[%.4f,%.4f,%.4f]\n",
          match->GetActualTime_ms(),phase,gap,(resolved-current).GetLength(),penetration,sweep,incoming.GetLength(),outgoing.GetLength(),resolved.coords[0],resolved.coords[1],resolved.coords[2]);
      }
    }
  }
  chestPreviousBall=ball->Predict(0);
  if(GetConfiguration()->GetBool("training_telemetry",false) && match->GetActualTime_ms()%20==0)
    printf("TRAINING_CHEST_STATE t=%lu phase=%.3f blend=%.4f gap=%.5f touched=%d root_motion=%.5f\n",match->GetActualTime_ms(),phase,contactPoseBlend,gap,chestTouched?1:0,chestAppliedMotion.GetLength());
}

Vector3 HumanoidBase::ChestRootMotion(float phase) const {
  if(!chestAnimation || chestAnimation->GetVariable("root_motion")!="true")return Vector3(0);
  phase=clamp(phase,0.0f,float(chestAnimation->GetEffectiveFrameCount()));
  const int frame=int(phase);Quaternion unused;Vector3 a,b;
  chestAnimation->GetKeyFrame("player",frame,unused,a);
  chestAnimation->GetKeyFrame("player",std::min(frame+1,chestAnimation->GetEffectiveFrameCount()),unused,b);
  return (a*(1-(phase-frame))+b*(phase-frame)).Get2D();
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
  if(!TrainingEnabled() || !player->GetExternalController() || fetchedChestPhase>=0)return;
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
  if(!TrainingEnabled())return;
  Ball *ball=match->GetBall();ball->CalculatePrediction();
  const Vector3 current=ball->Predict(0),incoming=ball->GetMovement();
  const Vector3 previous=contactPreviousBallValid?contactPreviousBall:current;
  contactPreviousBall=current;contactPreviousBallValid=true;
  if(match->GetActualTime_ms()<bodyContactUntil_ms || current.coords[2]<.45f || incoming.GetLength()<2 ||
      (current-spatialState.position-Vector3(0,0,1)).GetLength()>1.25f ||
      static_cast<Player*>(player)->GetLastTouchBias(350)>.01f)return;
  if(!match->TrainingReceivingBall() && !chestActive && chestCooldown_ms<=match->GetActualTime_ms())return;
  Quaternion local[13],global[13];Vector3 positions[13];
  std::copy(contactLocal,contactLocal+13,local);std::copy(contactPositions,contactPositions+13,positions);
  const bool chestTail=!chestActive && currentAnim->touchFrame<0 && chestCooldown_ms>match->GetActualTime_ms() &&
      match->GetActualTime_ms()<chestStarted_ms+180;
  if((chestActive || chestTail) && contactPoseBlend<.999f) {
    Quaternion nativeLocal[13],nativeGlobal[13];Vector3 nativePositions[13];
    SampleContactAnimation(currentAnim->anim,float(currentAnim->frameNum),animApplyBuffer.position,
        animApplyBuffer.orientation,false,nativeLocal,nativeGlobal,nativePositions);
    for(unsigned i=0;i<13;++i)local[i]=nativeLocal[i].GetSlerped(contactPoseBlend,local[i]).GetNormalized();
    positions[0]=nativePositions[0]*(1-contactPoseBlend)+positions[0]*contactPoseBlend;
  }
  ContactForwardKinematics(local,global,positions);
  Vector3 point,surface;std::string part;float fraction=-1;
  for(unsigned sample=0;sample<=8;++sample) {
    const float u=sample/8.0f;point=previous*(1-u)+current*u;
    if(ContactSurface(point,"",global,positions,&surface,&part)<=.0005f) {fraction=u;break;}
  }
  if(fraction<0)return;
  float low=std::max(0.0f,fraction-.125f),high=fraction;
  for(unsigned iteration=0;iteration<16;++iteration) {
    const float u=(low+high)*.5f;
    if(ContactSurface(previous*(1-u)+current*u,"",global,positions)>.0005f)low=u;else high=u;
  }
  point=previous*(1-high)+current*high;
  ContactSurface(point,"",global,positions,&surface,&part);
  const Vector3 normal=(point-surface).GetNormalized(spatialState.bodyDirectionVec);
  const float inward=incoming.GetDotProduct(normal);
  if(inward>=-.2f)return;
  const Vector3 outgoing=(incoming-normal*inward)*.8f-normal*inward*.3f;
  const Vector3 resolved=surface+normal*.1105f+outgoing*(1-high)*.01f;
  if((resolved-current).GetLength()>.12f)return;
  ball->ResolveBodyContact(resolved,outgoing);bodyContactUntil_ms=match->GetActualTime_ms()+60;
  contactPreviousBall=resolved;
  auto *actor=static_cast<Player*>(player);actor->GetTeam()->SetLastTouchPlayer(actor,e_TouchType_Accidental);
  actor->UpdatePossessionStats(false);ball->TriggerBallTouchSound(.15f);
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("TRAINING_BODY_TOUCH t=%lu part=%s correction=%.6f sweep=%.5f speed_before=%.5f speed_after=%.5f\n",
      match->GetActualTime_ms(),part.c_str(),(resolved-current).GetLength(),high,incoming.GetLength(),outgoing.GetLength());
}

void HumanoidBase::UpdateTrainingContactPose() {
  contactPoseBlend=0;
  if(!TrainingEnabled())return;
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
  if(!chestActive && currentAnim->touchFrame<0 && chestAnimation && chestPhase>0 && chestPhase<=chestAnimation->GetEffectiveFrameCount() &&
      match->GetActualTime_ms()<chestStarted_ms+180 && chestCooldown_ms>match->GetActualTime_ms()) {
    chestPhase=std::min(chestPhase+1,float(chestAnimation->GetEffectiveFrameCount()));
    contactPoseBlend=ease(1-float(match->GetActualTime_ms()-chestStarted_ms)/180);
    SampleContactAnimation(chestAnimation.get(),chestPhase,root,chestAngle,true,contactLocal,contactGlobal,contactPositions);
    return;
  }
  if(GetConfiguration()->GetBool("training_telemetry",false) && currentAnim->touchFrame>=0 && match->GetActualTime_ms()%20==0) {
    const Vector3 point=match->GetBall()->Predict(0),next=match->GetBall()->Predict(10);
    printf("TRAINING_NATIVE_GEOMETRY t=%lu frame=%d contact_frame=%d left=%.5f right=%.5f next_left=%.5f next_right=%.5f touched=%d\n",
      match->GetActualTime_ms(),currentAnim->frameNum,currentAnim->touchFrame,
      ContactSurface(point,"left_foot",contactGlobal,contactPositions),ContactSurface(point,"right_foot",contactGlobal,contactPositions),
      ContactSurface(next,"left_foot",contactGlobal,contactPositions),ContactSurface(next,"right_foot",contactGlobal,contactPositions),currentAnim->touchMade?1:0);
  }
  if(chestActive || dribbleLoopRequested)return;
  if(currentAnim->touchFrame<0) {
    if(match->TrainingReceivingBall())contactPoseBlend=1;
    return;
  }
  const int remaining=currentAnim->touchFrame-currentAnim->frameNum;
  if(remaining>20 || remaining< -14)return;
  contactPoseBlend=ease((20-remaining)/10.0f)*ease((remaining+14)/9.0f);
  // Authored joint rotations stay intact. Contact is planned with the
  // native whole-player approach, never a late per-leg reach adjustment.

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
  if(!TrainingEnabled() || fetchedContactBlend<=0)return;
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
  float renderedFootShift=0;
  // Interpolating a leg and a moving sphere independently can put the shoe
  // inside the ball between physical samples. Yield with the leg, retaining
  // its lengths and shoe orientation; never add a second impulse to the ball.
  for(unsigned side=0;side<2;++side) {
    const std::string part=side?"right_ankle":"left_ankle";
    Vector3 surface;
    if(ContactSurface(sphere,part,global,positions,&surface)>=.0005f)continue;
    const unsigned ankle=side?12:9;
    const auto &lo=pes3NativeReference.footMin[side],&hi=pes3NativeReference.footMax[side];
    const Vector3 center=positions[ankle]+global[ankle]*Vector3((lo[0]+hi[0])*.5f,
        (lo[1]+hi[1])*.5f,(lo[2]+hi[2])*.5f)*zMultiplier;
    const Vector3 away=(center-sphere).Get2D().GetNormalized(global[0]*Vector3(0,1,0));
    // An extended leg may not yield along its heel/centre direction. Use
    // the actual skin normal and lateral alternatives before lifting it.
    const Vector3 normal=(surface-sphere).GetNormalized(away);
    const Vector3 lateral=global[0]*Vector3(1,0,0);
    const Vector3 directions[]={normal,normal.Get2D().GetNormalized(away),away,
      lateral,-lateral,(away+Vector3(0,0,1)).GetNormalized(0),Vector3(0,0,1)};
    Quaternion bestLocal[13],bestGlobal[13];Vector3 bestPositions[13];
    float bestShift=100;
    for(const auto &direction:directions) {
      Quaternion trialLocal[13],trialGlobal[13];Vector3 trialPositions[13];
      auto trial=[&](float distance) {
        std::copy(local,local+13,trialLocal);std::copy(global,global+13,trialGlobal);
        std::copy(positions,positions+13,trialPositions);
        FitContactLeg(side,direction*distance,trialLocal,trialGlobal,trialPositions);
        return ContactSurface(sphere,part,trialGlobal,trialPositions);
      };
      float low=0,high=0;
      // Find the first clear position: IK reach limits make the gap
      // non-monotonic, so checking only the far endpoint misses valid exits.
      for(unsigned sample=1;sample<=16;++sample) {
        const float distance=sample*.005f;
        if(trial(distance)>=.0005f){high=distance;break;}
        low=distance;
      }
      if(high==0)continue;
      for(unsigned iteration=0;iteration<16;++iteration) {
        const float distance=(low+high)*.5f;
        if(trial(distance)<.0005f)low=distance;else high=distance;
      }
      trial(high);
      const float shift=(trialPositions[ankle]-positions[ankle]).GetLength();
      if(shift<bestShift) {
        bestShift=shift;std::copy(trialLocal,trialLocal+13,bestLocal);
        std::copy(trialGlobal,trialGlobal+13,bestGlobal);std::copy(trialPositions,trialPositions+13,bestPositions);
      }
    }
    if(bestShift<100) {
      std::copy(bestLocal,bestLocal+13,local);std::copy(bestGlobal,bestGlobal+13,global);
      std::copy(bestPositions,bestPositions+13,positions);
      renderedFootShift=std::max(renderedFootShift,bestShift);
      for(unsigned i=side?10:7;i<(side?13:10);++i)
        nodeMap.at(pes3::nativeBoneNames[i])->SetRotation(local[i],false);
    }
  }
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
