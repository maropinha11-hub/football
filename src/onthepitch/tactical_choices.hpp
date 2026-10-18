#pragma once
namespace football_tactics {
enum class Choice { Native, BuildOut, Clearance, Cross, LongShot, Combination, Circulate };
struct Situation {
 float ownGoal=100,goal=100,width=0,pressureDistance=100;
 float outletOdds=0,crossOdds=0,shotOdds=0,returnOdds=0;
 bool defender=false,boxReceiver=false,returnRunner=false,settled=false;
 float possessionSeconds=0;
};
inline Choice choose(const Situation &s){
 if(!s.settled)return Choice::Native;
 if(s.defender&&s.ownGoal<26&&s.pressureDistance<1.5f&&s.outletOdds<.45f)return Choice::Clearance;
 if(s.returnRunner&&s.returnOdds>.76f&&s.pressureDistance>1.2f)return Choice::Combination;
 if(s.width>15&&s.goal<37&&s.boxReceiver&&s.crossOdds>.62f)return Choice::Cross;
 if(s.goal>18&&s.goal<31&&s.width<13&&s.shotOdds>.78f&&s.pressureDistance>1.6f)return Choice::LongShot;
 if(s.defender&&s.ownGoal<34&&s.outletOdds>.70f)return Choice::BuildOut;
 if(s.possessionSeconds>.65f&&s.outletOdds>.74f&&(s.goal>25||s.pressureDistance<3.f))return Choice::Circulate;
 return Choice::Native;
}
inline const char *name(Choice c){const char *names[]={"native","buildout","clearance","cross","long_shot","combination","circulate"};return names[int(c)];}
}
namespace football_tactics {
inline float requestScore(int type,float odds,float speed,float forward,float groundOdds,float range,float space){
 float bonus=0;
 if(type==0)bonus+=(speed<1.5f&&range<20?.10f:0);
 if(type==1)bonus+=(speed>2&&forward>.25f&&space>1.5f?.20f:0);
 if(type==2)bonus+=(groundOdds<.45f&&range>10?.22f:0)+(range>25?.10f:0)-(range<8?.25f:0);
 return odds+bonus;
}
}
