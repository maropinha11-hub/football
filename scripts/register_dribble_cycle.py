#!/usr/bin/env python3
"""Register both halves of the approved loop as native locomotion/control clips."""
from pathlib import Path
import math
root=Path(__file__).resolve().parents[1]
source=root/'data/media/training/DefenseJog_LoopF.anim'
tracks={}
for line in source.read_text().splitlines():
 if not line or line.startswith('<'):continue
 row=line.split(',');width=4 if row[0]=='player'else 5
 tracks[row[0]]={int(row[i]):list(map(float,row[i+1:i+width]))for i in range(1,len(row),width)}
def sample(name,t):
 keys=tracks[name];a=int(t);b=min(a+1,max(keys));u=t-a
 v=keys[a];w=keys[b]
 if name!='player'and sum(x*y for x,y in zip(v,w))<0:w=[-x for x in w]
 q=[x*(1-u)+y*u for x,y in zip(v,w)]
 if name!='player':
  length=math.sqrt(sum(x*x for x in q));q=[x/length for x in q]
 return q
def lean(q,angle):
 x,y,z,w=q;s=math.sin(angle/2);c=math.cos(angle/2)
 return [c*x+s*w,c*y-s*z,c*z+s*y,c*w-s*x]
for half in (0,1):
 for kind in ('movement','movement_walk','ballcontrol'):
  lines=[]
  for name in tracks:
   values=[name]
   for frame in range(31):
    q=sample(name,half*35+frame*35/30)
    if name=='player':q=[0,-frame*(.035 if kind=='movement'else .05),q[2]-.96]
    if name in ('middle','neck'):q=lean(q,.13 if name=='middle'else .12)
    values.extend([str(frame),*['%.9f'%x for x in q]])
   lines.append(','.join(values))
  if kind=='ballcontrol':lines.append('extension,football,21,0.0,-1.60,0.11')
  metadata={'type':'movement'if kind.startswith('movement')else kind,'baseanim':'false','steps':'1','starting_foot':'right'if half==0 else'left',
            'training_dribble':'true','source_phase_start':str(half*35),'source_phase_scale':'1.166666667'}
  if kind=='ballcontrol':metadata['touch_bodypart']='right_foot'if half==0 else'left_foot'
  lines.extend('<'+k+'>'+v+'</'+k+'>'for k,v in metadata.items())
  path=root/('data/media/training/DefenseJog_native_'+kind+'_'+str(half)+'.anim')
  path.write_text('\n'.join(lines)+'\n')
  print(path.relative_to(root))
