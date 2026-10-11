#include "pes3preview.hpp"
#include "../main.hpp"
#include "scene/objectfactory.hpp"
#include "managers/resourcemanagerpool.hpp"
#include "base/geometry/trianglemeshutils.hpp"
#include "../pes3/pes_skeleton_bind_bits.h"
#include <cstdio>
#include <memory>
#include <sstream>

using namespace blunted;
namespace {
// Display and body share the source/native orientation. Display fit is separate
// from source units and from the native player/ball collision geometry.
const float displayScale = 1.8f/670.5759f;
struct Vertex { Vector3 position, normal; };
void triangle(std::vector<Vertex>& out, Vector3 a, Vector3 b, Vector3 c) {
  const auto normal = (b-a).GetCrossProduct(c-a).GetNormalized(Vector3(0,0,1));
  out.push_back({a,normal}); out.push_back({b,normal}); out.push_back({c,normal});
}
void joint(std::vector<Vertex>& out, const Vector3& p) {
  const float r = 0.032f;
  const Vector3 sides[4] = {{r,0,0},{0,r,0},{-r,0,0},{0,-r,0}};
  for (int i=0;i<4;++i) {
    triangle(out,p+sides[i],p+sides[(i+1)%4],p+Vector3(0,0,r));
    triangle(out,p+sides[(i+1)%4],p+sides[i],p-Vector3(0,0,r));
  }
}
void link(std::vector<Vertex>& out, const Vector3& a, const Vector3& b) {
  const Vector3 d = b-a;
  // Keep a fixed vertex/index count across clips, including coincident nodes.
  // The native dynamic buffer retains its initial index topology.
  const auto axis=d.GetNormalized(Vector3(0,0,1));
  const auto u = axis.GetCrossProduct(std::fabs(axis.coords[2]) < 0.9f ?
      Vector3(0,0,1) : Vector3(1,0,0)).GetNormalized(0)*0.018f;
  const auto v = axis.GetCrossProduct(u);
  const Vector3 sides[4] = {u,v,-u,-v};
  for (int i=0;i<4;++i) {
    const auto j=(i+1)%4;
    triangle(out,a+sides[i],a+sides[j],b+sides[i]);
    triangle(out,a+sides[j],b+sides[j],b+sides[i]);
  }
}
unsigned buildMesh(GeometryData& mesh,const Material& material,const std::array<Vector3,19>& points) {
  std::vector<Vertex> vertices;
  for (unsigned i=0;i<19;++i) {
    joint(vertices,points[i]);
    const int parent=PES_SKELETON_PARENTS[i];
    if (parent>=0) link(vertices,points[parent],points[i]);
  }
  const unsigned count=vertices.size(), elements=GetTriangleMeshElementCount();
  std::unique_ptr<float[]> data(new float[count*3*elements]());
  std::vector<unsigned> indices;
  indices.reserve(count);
  for (unsigned i=0;i<count;++i) {
    indices.push_back(i);
    const Vector3 fields[]={vertices[i].position,vertices[i].normal,Vector3(0.5f,0.5f,0),Vector3(1,0,0),Vector3(0,1,0)};
    for (unsigned f=0;f<elements;++f)
      for (unsigned axis=0;axis<3;++axis) data[f*count*3+i*3+axis]=fields[f].coords[axis];
  }
  mesh.SetTriangleMesh(material,data.release(),count*3*elements,indices);
  return count;
}
}
PES3Preview::PES3Preview(boost::intrusive_ptr<Node> target) {
  rate = clamp(GetConfiguration()->GetReal("pes3_preview_units_per_second",60),1.0f,120.0f);
  if (!std::isfinite(rate)) rate = 60;
  if (!bank.load(GetConfiguration()->Get("pes3_animation_file","pes3/pes_animation_tracks.fpsa"),loadError)) {
    printf("PES3_BANK unavailable: %s\n",loadError.c_str());
    return;
  }
  if (!bank.sample(47,0,pose)) { loadError="Falha ao avaliar pose PES3"; return; }
  for (unsigned i=0;i<19;++i) referenceRotations[i]=pose.rig.bones[i].composed_rotation;
  for(unsigned i=0;i<19;++i) {
    const auto& p=pose.rig.bones[i].composed_translation;
    referencePoints[i]=pes3::scalePoint(pes3::sourcePointToNative({{p[0],p[1],p[2]}}),displayScale);
  }
  playback.select(47);
  // Load a named surface rather than depending on ASE submaterial ordering.
  material = Material{};
  material.diffuseTexture=ResourceManagerPool::GetInstance().GetManager<Surface>(e_ResourceType_Surface)
      ->Fetch("media/objects/helpers/green.png",true,true);
  material.shininess=1;
  material.specular_amount=0;
  material.self_illumination=Vector3(0.6f);
  geometry = static_pointer_cast<Geometry>(ObjectFactory::GetInstance().CreateObject("PES3 source rig",e_ObjectType_Geometry));
  GetScene3D()->CreateSystemObjects(geometry);
  auto data = boost::intrusive_ptr<Resource<GeometryData>>(new Resource<GeometryData>("pes3_preview_rig"));
  data->GetResource()->SetDynamic(true);
  std::array<Vector3,19> points;
  for (unsigned i=0;i<19;++i) {
    const auto& p=pose.rig.bones[i].composed_translation;
    points[i]=Vector3(p[0],p[2],-p[1])*displayScale;
  }
  // Initialize a complete indexed mesh before attaching its renderer. The
  // legacy geometry interpreter expects the initial index/material topology.
  buildMesh(*data->GetResource(),material,points);
  geometry->SetGeometryData(data);
  geometry->SetPosition(Vector3(0,0,-50),false);
  geometry->Disable();
  target->AddObject(geometry);
  printf("PES3_BANK ready clips=%u bones=19 gameplay_replaced=0\n",bank.count());
}
std::string PES3Preview::caption() const {
  if (!geometry) return "PES3: "+loadError;
  if (!visible) return "Estudo PES3 fechado. Treino normal ativo.";
  std::ostringstream text;
  text << "Estudo PES3: clip " << playback.clip << " fase " << playback.phase << '/' << bank.duration(playback.clip)
       << (playback.playing ? " | reproduzindo" : " | parado")
       << " | V: corpo " << (bodyEnabled ? "ON" : "OFF")
       << " | F8/F9: clip | F10: pausa | F11: +1 | C: capturados | F7: sair";
  return text.str();
}
std::string PES3Preview::toggle() { if (geometry) visible=!visible; return caption(); }
std::string PES3Preview::toggleBody() {
  if (visible && geometry) bodyEnabled=!bodyEnabled;
  return caption();
}
void PES3Preview::releaseBodyForGameplay() {
  if (bodyEnabled) {
    bodyEnabled=false;
    if (GetConfiguration()->GetBool("training_telemetry",false)) printf("PES3_BODY released reason=gameplay_input\n");
  }
}
bool PES3Preview::bodyPose(const pes3::NativeBind& reference,pes3::NativePose& out) const {
  if(!fetched.visible||!fetched.body)return false;
  pes3::SourcePoints points;
  for(unsigned i=0;i<19;++i)for(unsigned a=0;a<3;++a)points[i][a]=fetched.points[i].coords[a];
  return pes3::retargetSkeleton(fetched.rotations,referenceRotations,points,referencePoints,reference,out);
}
std::string PES3Preview::select(int offset) {
  if (visible && geometry) {
    const int count=bank.count();
    const bool playing=playback.playing;
    playback.select((int(playback.clip)+offset+count)%count); playback.playing=playing; poseDirty=true;
  }
  return caption();
}
std::string PES3Preview::capturedClip() {
  // Clip IDs observed in the ten states. These are not guessed action labels.
  static const unsigned captured[]={47,236,313,304,224,219,269,120,372,264,206,797,275,317,366};
  if (visible && geometry) {
    const bool playing=playback.playing;
    playback.select(captured[capturedIndex]);
    playback.playing=playing;
    capturedIndex=(capturedIndex+1)%(sizeof(captured)/sizeof(captured[0])); poseDirty=true;
  }
  return caption();
}
std::string PES3Preview::pause() {
  if (visible && geometry) {
    if (playback.phase>=bank.duration(playback.clip)) { playback.phase=0; poseDirty=true; }
    playback.playing=!playback.playing;
    poseDirty=true;
  }
  return caption();
}
std::string PES3Preview::step() {
  if (visible && geometry) { playback.step(bank.duration(playback.clip)); poseDirty=true; }
  return caption();
}
void PES3Preview::process(bool matchPaused) {
  if (!visible || !geometry) return;
  if (!matchPaused && playback.playing) {
    playback.advance(0.01f,rate,bank.duration(playback.clip)); poseDirty=true;
  }
  if (poseDirty) {
    if (!bank.sample(playback.clip,playback.phase,pose)) {
      visible=false; loadError="Pose PES3 fora do dominio verificado";
      fprintf(stderr,"PES3_PREVIEW rejected clip=%u phase=%g\n",playback.clip,playback.phase);
      return;
    }
    poseDirty=false; ++revision;
    if (GetConfiguration()->GetBool("training_telemetry",false)) {
      const auto& p=pose.rig.bones[16].composed_translation;
      printf("PES3_PREVIEW clip=%u phase=%.6f playing=%d revision=%lu point16=[%.6f,%.6f,%.6f]\n",
             playback.clip,playback.phase,playback.playing?1:0,revision,p[0],p[1],p[2]);
      fflush(stdout);
    }
  }
}
void PES3Preview::prepare(const Vector3& position,const Vector3& direction) {
  buffer.visible=visible && bool(geometry);
  buffer.body=bodyEnabled;
  if (!buffer.visible) return;
  const Vector3 right(direction.coords[1],-direction.coords[0],0);
  buffer.position=position.Get2D()+direction*2.8f+right*1.1f;
  buffer.rotation.SetAngleAxis(std::atan2(direction.coords[1],direction.coords[0])+0.5f*pi,Vector3(0,0,1));
  for (unsigned i=0;i<19;++i) {
    const auto& p=pose.rig.bones[i].composed_translation;
    const auto converted=pes3::sourcePointToNative({{p[0],p[1],p[2]}});
    buffer.points[i]=Vector3(converted[0],converted[1],converted[2])*displayScale;
    buffer.rotations[i]=pose.rig.bones[i].composed_rotation;
  }
  buffer.revision=revision;
  buffer.clip=playback.clip; buffer.phase=playback.phase;
}
void PES3Preview::put() {
  if (!geometry) return;
  if (!fetched.visible) { geometry->Disable(); return; }
  geometry->Enable();
  geometry->SetPosition(fetched.position,false);
  geometry->SetRotation(fetched.rotation,false);
  if (renderedRevision==fetched.revision) return;
  renderedRevision=fetched.revision;
  auto resource=geometry->GetGeometryData();
  unsigned count=0;
  { boost::mutex::scoped_lock lock(resource->resourceMutex);
    count=buildMesh(*resource->GetResource(),material,fetched.points);
  }
  geometry->OnUpdateGeometryData(false);
  if (renderedClip!=fetched.clip && GetConfiguration()->GetBool("training_telemetry",false)) {
    renderedClip=fetched.clip;
    printf("PES3_RENDER clip=%u phase=%.6f bones=19 vertices=%u\n",fetched.clip,fetched.phase,count);
    fflush(stdout);
  }
}
