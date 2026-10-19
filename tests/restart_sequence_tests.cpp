#include "onthepitch/restart_sequence.hpp"
#include <iostream>

int main(){
  football_rules::RestartSequence restart;int failures=0,checks=0;
  auto check=[&](bool ok,const char *name){++checks;if(!ok){++failures;std::cerr<<name<<'\n';}};
  restart.sync(true,100);
  check(!restart.prepareDue(99,100),"prepare before deadline");
  check(restart.prepareDue(110,100),"missed exact prepare timestamp");
  check(!restart.startDue(300,200),"start before preparation");
  restart.authorize();check(!restart.authorized(),"unprepared authorization");
  restart.prepare();check(!restart.prepareDue(500,100),"duplicate preparation");
  check(!restart.contact(200,200,true),"contact before authorization");
  check(restart.startDue(210,200),"missed exact whistle timestamp");
  restart.authorize();check(!restart.startDue(500,200),"duplicate whistle");
  check(!restart.contact(199,200,true),"pre-whistle kick");
  check(!restart.contact(250,200,false)&&!restart.hasReleased(),"missed animation or wrong player released play");
  check(restart.contact(250,200,true)&&restart.hasReleased(),"real taker contact did not release play");
  check(!restart.contact(260,200,true),"duplicate release");
  restart.sync(true,100);check(restart.hasReleased(),"same event lost its state");
  restart.sync(true,400);check(!restart.isPrepared()&&!restart.authorized()&&!restart.hasReleased(),"next event reused old state");
  restart.prepare();restart.sync(false,400);check(!restart.isPrepared(),"inactive event retained state");
  std::cout<<checks<<" checks, "<<failures<<" failures\n";return failures?1:0;
}
