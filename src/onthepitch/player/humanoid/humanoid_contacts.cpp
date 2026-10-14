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
  const float angle=spatialState.angle;
  const Vector3 root=spatialState.position;
  SampleContactAnimation(chestAnimation.get(),chestContactFrame,root,angle,true,local,global,positions);
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
  Quaternion local[13],global[13];Vector3 positions[13];
  std::copy(contactLocal,contactLocal+13,local);std::copy(contactPositions,contactPositions+13,positions);
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
  const int remaining=currentAnim->touchFrame-currentAnim->frameNum;
  const float nativeBlend=currentAnim->touchFrame>=0 ?
      ease((20-remaining)/10.0f)*ease((remaining+14)/9.0f) : 0;
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
  contactPoseBlend=nativeBlend*dribbleTrialBlend;
  // Authored joint rotations stay intact. Contact is planned with the
  // native whole-player approach, never a late per-leg reach adjustment.

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
