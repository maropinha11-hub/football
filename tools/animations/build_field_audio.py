"""Deterministic original PCM effects: turf steps, breathing and outdoor air."""
import math,random,struct,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'data/media/sounds'
RATE=22050
def write(name,seconds,signal):
 samples=[signal(i/RATE)for i in range(int(seconds*RATE))]
 peak=max(.01,max(map(abs,samples)));samples=[int(max(-1,min(1,x/peak*.72))*32767)for x in samples]
 with wave.open(str(ROOT/name),'wb')as f:
  f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(struct.pack('<'+'h'*len(samples),*samples))
def generate():
 for variant in range(2):
  rng=random.Random(71+variant);filtered=0
  def foot(t):
   nonlocal filtered
   noise=rng.uniform(-1,1);filtered=.75*filtered+.25*noise
   return .6*math.sin(2*math.pi*(92+variant*17)*t)*math.exp(-35*t)+filtered*(math.exp(-20*t)+.55*math.exp(-((t-.075)/.045)**2))
  write('turfstep'+str(variant)+'.wav',.25,foot)
 rng=random.Random(137);low=0
 def breath(t):
  nonlocal low
  noise=rng.uniform(-1,1);low=.90*low+.1*noise
  phase=t/3.2;envelope=max(0,math.sin(2*math.pi*phase))**2*.50+max(0,-math.sin(2*math.pi*phase))**2*.80
  return (noise-low)*envelope*(.7+.3*math.sin(2*math.pi*650*t))
 write('breathing.wav',3.2,breath)
 rng=random.Random(281);low=0
 def field(t):
  nonlocal low
  low=.985*low+.015*rng.uniform(-1,1)
  edge=math.sin(math.pi*min(t/.4,(12-t)/.4,1))**2 if t<.2 or t>11.8 else 1
  bird=.04*math.sin(2*math.pi*(2300+180*math.sin(2*math.pi*3*t))*t)*max(0,math.sin(2*math.pi*t/4))**16
  return edge*(low*(.7+.3*math.sin(2*math.pi*t/12))+bird)
 write('fieldair.wav',12,field)
if __name__=='__main__':generate()
