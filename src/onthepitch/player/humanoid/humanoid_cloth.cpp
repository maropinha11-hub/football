#include "humanoidbase.hpp"
#include "shirt_cloth.hpp"
#include "../../../main.hpp"
#include "../../match.hpp"
#include "../player.hpp"

void HumanoidBase::PutShirtCloth(unsigned subgeom,std::vector<MaterializedTriangleMesh> &meshes){
  if(!fetchedPhysicalRig || GetConfiguration()->GetBool("training_animation_body",true) || !GetConfiguration()->GetBool("training_shirt_cloth",true))return;
  if(shirtCloth.size()!=fullbodySubgeomCount){shirtCloth.resize(fullbodySubgeomCount);shirtClothTime.resize(fullbodySubgeomCount,0);}
  auto &mesh=meshes[subgeom];const auto &weighted=weightedVerticesVec[subgeom];
  const int offset=uniqueFullbodyMesh[subgeom].size/GetTriangleMeshElementCount();
  std::vector<football_physics::Vec> rest,targets,normals;
  std::vector<float> mobility;
  for(const auto &vertex:weighted){
    const unsigned id=vertex.vertexID*3;const auto &data=uniqueFullbodyMesh[subgeom];
    Vector3 original(data.data[id],data.data[id+1],data.data[id+2]);
    Vector3 target(mesh.vertices[id],mesh.vertices[id+1],mesh.vertices[id+2]);target+=fullbodyOffset;
    rest.push_back({{original.coords[0],original.coords[1],original.coords[2]}});
    targets.push_back({{target.coords[0],target.coords[1],target.coords[2]}});
    normals.push_back({{mesh.vertices[id+offset],mesh.vertices[id+offset+1],mesh.vertices[id+offset+2]}});
    float trunk=0;for(auto bone:vertex.bones)if(bone.jointID==0 || bone.jointID==1)trunk+=bone.weight;
    const float height=original.coords[2]/zMultiplier;
    mobility.push_back(trunk>.95f && std::fabs(original.coords[0]/zMultiplier)<.27f?
      clamp((height-.94f)/.07f,0.f,1.f)*clamp((1.43f-height)/.10f,0.f,1.f):0.f);
  }
  if(!shirtCloth[subgeom]){
    shirtCloth[subgeom].reset(new football_physics::ShirtCloth);
    std::vector<unsigned> triangles(mesh.indices.begin(),mesh.indices.end());
    shirtCloth[subgeom]->configure(rest,triangles,mobility);
  }
  auto &cloth=*shirtCloth[subgeom];if(!cloth.movable())return;
  const unsigned long now=fetchedbuf_animApplyBuffer.snapshotTime_ms;
  const float dt=shirtClothTime[subgeom] && now>=shirtClothTime[subgeom]?std::min(.10f,(now-shirtClothTime[subgeom])*.001f):0;
  shirtClothTime[subgeom]=now;
  cloth.step(targets,normals,dt,{{fetchedPhysicalGripPoint.coords[0],fetchedPhysicalGripPoint.coords[1],fetchedPhysicalGripPoint.coords[2]}},
    {{fetchedPhysicalGripForce.coords[0],fetchedPhysicalGripForce.coords[1],fetchedPhysicalGripForce.coords[2]}});
  const auto &positions=cloth.positions();
  for(unsigned i=0;i<weighted.size();++i)if(mobility[i]>0){
    const auto p=positions[i];const unsigned id=weighted[i].vertexID*3;
    for(unsigned c=0;c<3;++c)mesh.vertices[id+c]=p[c]-fullbodyOffset.coords[c];
  }
  // Recompute the deformed shirt's normals instead of retaining a flat
  // normal field while its vertices move. Other materials remain untouched.
  std::vector<Vector3> deformed(weighted.size(),Vector3(0));
  for(unsigned t=0;t+2<mesh.indices.size();t+=3){
    const unsigned a=mesh.indices[t],b=mesh.indices[t+1],c=mesh.indices[t+2];
    Vector3 pa(mesh.vertices[a*3],mesh.vertices[a*3+1],mesh.vertices[a*3+2]);
    Vector3 pb(mesh.vertices[b*3],mesh.vertices[b*3+1],mesh.vertices[b*3+2]);
    Vector3 pc(mesh.vertices[c*3],mesh.vertices[c*3+1],mesh.vertices[c*3+2]);
    const Vector3 n=(pb-pa).GetCrossProduct(pc-pa);deformed[a]+=n;deformed[b]+=n;deformed[c]+=n;
  }
  for(unsigned i=0;i<weighted.size();++i)if(mobility[i]>0 && deformed[i].GetLength()>.000001f){
    Vector3 n=deformed[i].GetNormalized(0);Vector3 previous(normals[i][0],normals[i][1],normals[i][2]);
    if(n.GetDotProduct(previous)<0)n=-n;
    for(unsigned c=0;c<3;++c)mesh.vertices[weighted[i].vertexID*3+offset+c]=n.coords[c];
  }
  if(GetConfiguration()->GetBool("training_telemetry",false) && dt>0 && cloth.reportDue(now))
    printf("PHYSICAL_CLOTH t=%lu actor=%d vertices=%u displacement=%.6f stretch=%.5f grip=%.3f\n",now,player->GetID(),cloth.movable(),cloth.displacement(),cloth.stretch(),fetchedPhysicalGripForce.GetLength());
}
