#include "match.hpp"
#include "../main.hpp"
#include "player/humanoid/humanoidbase.hpp"
#include "scene/resources/soundbuffer.hpp"
#include "scene/objectfactory.hpp"
#include "managers/resourcemanagerpool.hpp"
#include <cmath>

void Match::InitFieldAudio(){
  if(!TrainingEnabled())return;
  auto make=[&](const std::string &file,const std::string &name,bool loop){
    auto sound=boost::static_pointer_cast<Sound>(ObjectFactory::GetInstance().CreateObject(name,e_ObjectType_Sound));
    GetScene3D()->CreateSystemObjects(sound);
    sound->SetSoundBuffer(ResourceManagerPool::GetInstance().GetManager<SoundBuffer>(e_ResourceType_SoundBuffer)->Fetch("media/sounds/"+file,true,true));
    sound->SetGain(0);sound->SetLoop(loop);sound->SetRadius(loop?100.f:22.f);GetScene3D()->AddObject(sound);
    if(loop)sound->Poke(e_SystemType_Audio);return sound;
  };
  fieldBreath=make("breathing.wav","playerbreath",true);fieldAir=make("fieldair.wav","outdoorair",true);
}

void Match::ProcessFieldAudio(){
  if(!fieldBreath||!trainingPlayer)return;
  const float volume=clamp(GetConfiguration()->GetReal("audio_volume",.35f),0.f,1.f);
  const Vector3 listener=trainingPlayer->GetPosition();
  const float wanted=clamp(trainingPlayer->GetMovement().GetLength()/6.5f,0.f,1.f);
  fieldEffort+=(wanted-fieldEffort)*(wanted>fieldEffort?.012f:.002f);
  fieldBreath->SetPosition(listener+Vector3(0,0,1.5f));fieldBreath->SetPitch(.88f+.30f*fieldEffort);
  const float breath=volume*GetConfiguration()->GetReal("audio_breath_gain",.22f)*(.12f+.88f*fieldEffort);
  fieldBreath->SetGain(breath);fieldAir->SetPosition(listener);
  fieldAir->SetGain(volume*GetConfiguration()->GetReal("audio_field_gain",.13f));
  if(GetConfiguration()->GetBool("training_telemetry",false)&&actualTime_ms%500==0)
    printf("FIELD_AUDIO t=%lu effort=%.5f breath=%.5f footsteps=0\n",actualTime_ms,fieldEffort,breath);
}
