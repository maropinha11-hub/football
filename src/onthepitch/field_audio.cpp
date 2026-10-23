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
  for(unsigned i=0;i<4;++i)fieldSteps[i]=make("turfstep"+int_to_str(i%2)+".wav","fieldstep"+int_to_str(i),false);
  fieldBreath=make("breathing.wav","playerbreath",true);fieldAir=make("fieldair.wav","outdoorair",true);
}

void Match::ProcessFieldAudio(){
  if(!fieldBreath||!trainingPlayer)return;
  const float volume=clamp(GetConfiguration()->GetReal("audio_volume",.35f),0.f,1.f);
  const Vector3 listener=trainingPlayer->GetPosition();
  std::vector<Player*> actors;teams[0]->GetActivePlayers(actors);teams[1]->GetActivePlayers(actors);
  if(!PlayerMatchEnabled()){actors.clear();actors.push_back(trainingPlayer);if(trainingPartner)actors.push_back(trainingPartner);}
  for(auto *actor:actors){
    auto *body=actor->GetHumanoid();auto &track=fieldFootHistory[actor->GetID()];
    for(unsigned side=0;side<2;++side){
      const auto foot=body->GetContactFootPosition(side);const float height=foot.coords[2];
      const float speed=actor->GetMovement().Get2D().GetLength();const float range=(foot-listener).Get2D().GetLength();
      const bool landed=track.ready&&track.height[side]>.085f&&height<=.085f;
      if(landed&&speed>.45f&&range<19&&actualTime_ms>track.last[side]+240&&!body->PhysicalRigBusy()){
        auto sound=fieldSteps[(fieldStepVoice++)%4];sound->SetPosition(foot);sound->SetPitch(.94f+.05f*(side?1:-1));
        const float gain=volume*GetConfiguration()->GetReal("audio_turf_gain",.75f)*(.35f+.06f*std::min(7.f,speed))*clamp(1-range/22.f,0.f,1.f);
        sound->SetGain(gain);sound->Poke(e_SystemType_Audio);track.last[side]=actualTime_ms;
        if(GetConfiguration()->GetBool("training_telemetry",false))printf("FIELD_STEP t=%lu actor=%d foot=%u gain=%.5f z=%.5f\n",actualTime_ms,actor->GetID(),side,gain,height);
      }
      track.height[side]=height;
    }
    track.ready=true;
  }
  const float wanted=clamp(trainingPlayer->GetMovement().GetLength()/6.5f,0.f,1.f);
  fieldEffort+=(wanted-fieldEffort)*(wanted>fieldEffort?.012f:.002f);
  fieldBreath->SetPosition(listener+Vector3(0,0,1.5f));fieldBreath->SetPitch(.88f+.30f*fieldEffort);
  const float breath=volume*GetConfiguration()->GetReal("audio_breath_gain",.22f)*(.12f+.88f*fieldEffort);
  fieldBreath->SetGain(breath);fieldAir->SetPosition(listener);
  fieldAir->SetGain(volume*GetConfiguration()->GetReal("audio_field_gain",.13f));
  if(GetConfiguration()->GetBool("training_telemetry",false)&&actualTime_ms%500==0)
    printf("FIELD_AUDIO t=%lu effort=%.5f breath=%.5f voices=%u\n",actualTime_ms,fieldEffort,breath,fieldStepVoice);
}
