#pragma once

namespace football_rules {
// A restart is an event with preparation, authorization and a real contact.
// A completed animation is not evidence that the ball was released.
class RestartSequence {
 public:
  void reset(){stamp=~0ul;prepared=ready=released=false;}
  void sync(bool active,unsigned long stop){if(!active||stamp!=stop){reset();stamp=stop;}}
  bool prepareDue(unsigned long now,unsigned long due)const{return !prepared&&now>=due;}
  bool startDue(unsigned long now,unsigned long due)const{return prepared&&!ready&&now>=due;}
  void prepare(){prepared=true;}
  void authorize(){if(prepared)ready=true;}
  bool contact(unsigned long now,unsigned long start,bool actualTakerStrike){
    if(!ready||released||now<start||!actualTakerStrike)return false;
    released=true;return true;
  }
  bool isPrepared()const{return prepared;}
  bool authorized()const{return ready;}
  bool hasReleased()const{return released;}
 private:
  unsigned long stamp=~0ul;
  bool prepared=false,ready=false,released=false;
};
}
