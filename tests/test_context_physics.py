"""Physical invariants and contextual choices used by the actual game."""
import ctypes as C
import math
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class ContextPhysics(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.directory=tempfile.TemporaryDirectory();library=Path(cls.directory.name)/'context.so'
  source=r'''
#include "onthepitch/ball_turf.hpp"
#include "onthepitch/physical_match_rules.hpp"
#include "onthepitch/tactical_choices.hpp"
#include "onthepitch/keeper_trajectory.hpp"
extern "C" void surface(float x,float y,float r,float *out){auto s=football_turf::sample(x,y,r);out[0]=s.height;out[1]=s.dx;out[2]=s.dy;out[3]=s.restitution;out[4]=s.resistance;}
extern "C" void collide(float *p,float *v,float r,float bounce,float *out){football_turf::Vec pos{{p[0],p[1],p[2]}},vel{{v[0],v[1],v[2]}};auto q=football_turf::contact(pos,vel,r,bounce,.06f);for(int i=0;i<3;++i){p[i]=pos[i];v[i]=vel[i];}out[0]=q.contact;out[1]=q.energyBefore;out[2]=q.energyAfter;}
extern "C" bool foul(float age,float force,bool fall){return football_rules::excessiveHold(age,force,fall);}
extern "C" bool receive(float facing,float speed,float distance){return football_rules::rearReception(facing,speed,distance);}
extern "C" void tackle(bool sliding,float speed,bool behind,bool ballFirst,float *out){auto t=football_rules::tackle(sliding,speed,behind,ballFirst);out[0]=t.impulse;out[1]=t.fall;out[2]=t.foul;out[3]=t.severity;}
extern "C" float load(float p,float s,float t,bool h){return football_rules::strikeLoad(p,s,t,h);}
extern "C" float cut(float speed,float request,float dot){return football_rules::cutImpulse(speed,request,dot);}
extern "C" bool reception(float gap,float height,float closing,float speed,bool free){return football_rules::incomingReception(gap,height,closing,speed,free);}
extern "C" bool heel(float face,float speed,float power,float pressure,float own,unsigned long elapsed){return football_rules::rareHeel(face,speed,power,pressure,own,elapsed);}
extern "C" float angle(float goal,float ball,float defender){return football_keeper::closeAngleDepth(goal,ball,defender);}
extern "C" int circulate(float age,float outlet){football_tactics::Situation s;s.settled=true;s.possessionSeconds=age;s.outletOdds=outlet;return int(football_tactics::choose(s));}
extern "C" int tactic(float own,float goal,float width,float pressure,float outlet,float cross,float shot,float ret,bool defender,bool box,bool runner,bool settled){football_tactics::Situation s;s.ownGoal=own;s.goal=goal;s.width=width;s.pressureDistance=pressure;s.outletOdds=outlet;s.crossOdds=cross;s.shotOdds=shot;s.returnOdds=ret;s.defender=defender;s.boxReceiver=box;s.returnRunner=runner;s.settled=settled;return int(football_tactics::choose(s));}
extern "C" float request(int type,float odds,float speed,float forward,float ground,float range,float space){return football_tactics::requestScore(type,odds,speed,forward,ground,range,space);}
extern "C" bool crossing(float *a,float *b,float side,float *y){return football_keeper::goalCrossing({{a[0],a[1],a[2]}},{{b[0],b[1],b[2]}},side,52.5f,3.8f,2.55f,*y);}
'''
  subprocess.run(['g++','-std=c++14','-O2','-shared','-fPIC','-I'+str(ROOT/'src'),'-x','c++','-','-o',str(library)],input=source,text=True,check=True)
  cls.lib=C.CDLL(str(library));f=C.c_float;b=C.c_bool;fp=C.POINTER(f)
  for name,args,result in [('cut',[f]*3,f),('reception',[f]*4+[b],b),('heel',[f]*5+[C.c_ulong],b),('angle',[f]*3,f),('circulate',[f]*2,C.c_int)]:
   fn=getattr(cls.lib,name);fn.argtypes=args;fn.restype=result
  for name,args,result in [('surface',[f,f,f,fp],None),('collide',[fp,fp,f,f,fp],None),('foul',[f,f,b],b),('receive',[f,f,f],b),('tackle',[b,f,b,b,fp],None),('load',[f,f,f,b],f),('tactic',[f]*8+[b]*4,C.c_int),('request',[C.c_int]+[f]*6,f),('crossing',[fp,fp,f,fp],b)]:
   fn=getattr(cls.lib,name);fn.argtypes=args;fn.restype=result
 @classmethod
 def tearDownClass(cls):cls.directory.cleanup()
 def field(self,x,y,r):
  values=(C.c_float*5)();self.lib.surface(x,y,r,values);return list(values)
 def contact(self,p,v,r=.65,bounce=.7):
  p=(C.c_float*3)(*p);v=(C.c_float*3)(*v);out=(C.c_float*3)();self.lib.collide(p,v,r,bounce,out);return list(p),list(v),list(out)
 def test_surface_is_bounded_static_and_not_a_time_kick(self):
  points=[(i*.31,j*.27)for i in range(-20,21)for j in range(-15,16)]
  heights=[]
  for x,y in points:
   s=self.field(x,y,.65);self.assertEqual(s,self.field(x,y,.65));heights.append(s[0]);self.assertTrue(0<=s[0]<.0101);self.assertLess(math.hypot(*s[1:3]),.1)
   self.assertTrue(.86<s[3]<=1 and .85<s[4]<1.15)
  self.assertGreater(max(heights)-min(heights),.006)
 def test_cut_loading_requires_speed_and_a_real_stop_or_reversal(self):
  self.assertEqual(self.lib.cut(4,4,-1),0);self.assertEqual(self.lib.cut(8,8,1),0)
  self.assertGreater(self.lib.cut(8,8,-1),90);self.assertGreater(self.lib.cut(8,0,0),60)
  self.assertLessEqual(self.lib.cut(20,8,-1),140)
 def test_reception_requires_a_reachable_free_arrival(self):
  self.assertTrue(self.lib.reception(.4,.12,6,6,True));self.assertTrue(self.lib.reception(.3,1.6,9,9,True))
  for args in [(1.5,1,6,6,True),(.4,3,6,6,True),(.4,1,-1,6,True),(.4,1,6,26,True),(.4,1,6,6,False)]:self.assertFalse(self.lib.reception(*args))
 def test_heel_is_reserved_for_rare_low_power_emergencies_far_from_own_goal(self):
  self.assertTrue(self.lib.heel(-1,1,.3,.4,40,31000))
  for args in [(-1,1,.3,.4,40,1000),(-1,1,.3,.4,10,31000),(-1,1,.9,.4,40,31000),(-1,1,.3,4,40,31000),(1,1,.3,.4,40,31000)]:self.assertFalse(self.lib.heel(*args))
 def test_keeper_closes_one_on_one_but_respects_cover_and_loose_ball(self):
  self.assertGreater(self.lib.angle(16,.6,8),5)
  self.assertEqual(self.lib.angle(16,.6,1),0);self.assertEqual(self.lib.angle(16,6,8),0);self.assertEqual(self.lib.angle(32,.6,8),0)
 def test_circulation_requires_a_completed_settled_possession_and_safe_outlet(self):
  self.assertEqual(self.lib.circulate(.9,.9),6);self.assertEqual(self.lib.circulate(.1,.9),0);self.assertEqual(self.lib.circulate(.9,.4),0)
 def test_surface_normals_match_the_actual_height(self):
  for x,y in [(i*.43,j*.37)for i in range(-3,4)for j in range(-3,4)]:
   s=self.field(x,y,.65);eps=.0005
   for axis in [0,1]:
    p=[x,y];q=[x,y];p[axis]+=eps;q[axis]-=eps
    finite=(self.field(*p,.65)[0]-self.field(*q,.65)[0])/(2*eps)
    self.assertAlmostEqual(finite,s[axis+1],delta=.00012)
 def test_flat_reference_has_no_terrain_modification(self):
  self.assertEqual(self.field(8,-7,0),[0,0,0,1,1]);p,v,r=self.contact([1,2,.11],[4,0,-1],r=0);self.assertEqual(v,[4,0,-1]);self.assertFalse(r[0])
 def test_contacts_do_not_create_kinetic_energy(self):
  rng=random.Random(29)
  for _ in range(2500):
   x,y=rng.uniform(-50,50),rng.uniform(-32,32);h=self.field(x,y,.65)[0]
   p,v,r=self.contact([x,y,.11+h-.001],[rng.uniform(-25,25),rng.uniform(-25,25),rng.uniform(-15,0)])
   self.assertTrue(r[0]);self.assertLessEqual(sum(x*x for x in v),r[1]+.0004);self.assertLessEqual(r[2],r[1]+.00001);self.assertGreaterEqual(p[2],.11+h-.00001)
 def test_a_ball_in_the_air_receives_no_surface_impulse(self):
  p,v,r=self.contact([0,0,1.3],[4,2,-3]);self.assertFalse(r[0]);self.assertEqual(v,[4,2,-3])
 def test_ground_at_rest_does_not_vibrate_or_launch(self):
  for x,y in [(0,0),(8,-2),(-23,11)]:
   h=self.field(x,y,.65)[0];p,v,r=self.contact([x,y,.11+h],[0,0,-.0981]);self.assertEqual(v,[0,0,0])
 def test_holding_requires_actual_excess_or_loss_of_balance(self):
  self.assertFalse(self.lib.foul(.2,180,False));self.assertFalse(self.lib.foul(2,0,True));self.assertFalse(self.lib.foul(3,30,False))
  self.assertTrue(self.lib.foul(.9,170,False));self.assertTrue(self.lib.foul(.3,80,True));self.assertTrue(self.lib.foul(1.8,90,False))
 def test_stronger_and_harder_actions_require_more_balance(self):
  self.assertGreater(self.lib.load(1,7,1.8,False),self.lib.load(.15,0,0,False)+.5);self.assertGreater(self.lib.load(.7,0,.5,True),.3)
 def test_tactical_choices_respect_space_and_danger(self):
  def choose(**k):
   x=dict(own=100,goal=40,width=0,pressure=5,outlet=0,cross=0,shot=0,ret=0,defender=False,box=False,runner=False,settled=True);x.update(k);return self.lib.tactic(*x.values())
  self.assertEqual(choose(own=18,defender=True,outlet=.85),1)
  self.assertEqual(choose(own=18,defender=True,outlet=.3,pressure=.9),2)
  self.assertEqual(choose(goal=28,width=21,box=True,cross=.8),3)
  self.assertEqual(choose(goal=24,shot=.9),4);self.assertEqual(choose(goal=24,shot=.4),0)
  self.assertEqual(choose(runner=True,ret=.9),5);self.assertEqual(choose(runner=True,ret=.2),0)
  self.assertEqual(choose(own=18,defender=True,outlet=.9,settled=False),0)
 def test_requested_pass_adapts_to_receiver_run_and_blocked_lane(self):
  def scores(speed,forward,ground,distance,space):return[self.lib.request(i,.65,speed,forward,ground,distance,space)for i in range(3)]
  self.assertEqual(max(range(3),key=lambda i:scores(0,0,.8,12,3)[i]),0)
  self.assertEqual(max(range(3),key=lambda i:scores(4,1,.7,18,5)[i]),1)
  self.assertEqual(max(range(3),key=lambda i:scores(1,0,.2,28,3)[i]),2)
 def test_back_to_ball_requires_a_turn_or_slow_close_control(self):
  self.assertTrue(self.lib.receive(1,9,1));self.assertTrue(self.lib.receive(-1,2,.4))
  self.assertFalse(self.lib.receive(-1,9,.4));self.assertFalse(self.lib.receive(-1,2,1))
 def test_tackles_distinguish_clean_ball_miss_stagger_and_fall(self):
  def tackle(slide,speed,behind,ball):
   out=(C.c_float*4)();self.lib.tackle(slide,speed,behind,ball,out);return list(out)
  clean=tackle(True,3,False,True);late=tackle(True,3,False,False);poke=tackle(False,1,False,False);reckless=tackle(True,7,True,True)
  self.assertEqual(clean[1:3],[1,0]);self.assertEqual(late[1:3],[1,1]);self.assertEqual(poke[1:3],[0,1])
  self.assertEqual(reckless[1:3],[1,1]);self.assertGreater(late[0],poke[0]);self.assertLessEqual(reckless[0],330)
 def test_keeper_distinguishes_goal_bound_high_and_wide_trajectories(self):
  def hit(a,b,side=1):
   x=(C.c_float*3)(*a);z=(C.c_float*3)(*b);y=C.c_float();return self.lib.crossing(x,z,side,C.byref(y)),y.value
  self.assertTrue(hit([50,1,1],[53,2,1])[0]);self.assertTrue(hit([-50,1,1],[-53,2,1],-1)[0])
  self.assertFalse(hit([50,1,4],[53,2,3])[0]);self.assertFalse(hit([50,8,1],[53,9,1])[0]);self.assertFalse(hit([50,1,1],[49,1,1])[0])
if __name__=='__main__':unittest.main()
