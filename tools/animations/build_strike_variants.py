"""Generate native action variations with unchanged root, legs and event times.
Ankle orientation changes smoothly around impact; the runtime rebinds the
marker to the resulting real shoe surface and checks actual ball contact.
No imported skeleton, locomotion track, time warp or capture is introduced.
"""
import hashlib,json,math,re
from pathlib import Path
from build_situational_catalog import ROOT,parse_source,sample,qmul,qnormalize,utility_hierarchy,contact_geometry

SOURCES=['pass/idle/000.anim','pass/walk/000.anim','pass/walk/045.anim','pass/sprint/000.anim',
 'shot/idle/020.anim','shot/walk/010_short.anim','shot/sprint/030.anim',
 'highpass/walk/000.anim','highpass/walk/080.anim','highpass/idle/020.anim',
 'pass/idle/090.anim','pass/walk/090.anim','pass/walk/135.anim','pass/sprint/045.anim','pass/sprint/090.anim',
 'shot/idle/090.anim','shot/walk/090_2step.anim','shot/sprint/090_2step.anim','shot/walk/180_turn.anim',
 'highpass/sprint/090.anim','highpass/walk/180_turn.anim']
STYLES={'inside':(0.,0.,-.15),'outside':(0.,0.,.18),'toe':(-.14,0.,0.),'knuckle':(-.075,.025,0.)}
def exp(v):
 n=math.sqrt(sum(x*x for x in v));return (*[x*math.sin(n/2)/max(n,1e-12)for x in v],math.cos(n/2))
def generate():
 rows=[];hierarchy=utility_hierarchy(ROOT)
 for relative in SOURCES:
  source=ROOT/'data/media/animations'/relative
  if not source.exists():continue
  tracks,events,metadata,raw=parse_source(source)
  at,ball=events[0];part,*_=contact_geometry(tracks,at,ball,hierarchy)
  if part not in ['left_foot','right_foot']:continue
  ankle=part.replace('foot','ankle');end=max(k[-1][0]for k in tracks.values())
  for style,axis in STYLES.items():
   if metadata['type']!='shot'and style in ['toe','knuckle']:continue
   text=raw.decode();lines=[]
   for line in text.splitlines():
    bone=line.split(',')[0]
    if bone not in [ankle,'middle','left_shoulder','right_shoulder']:lines.append(line);continue
    values=[bone]
    # Dense samples represent one smooth support curve; first and last poses
    # match the original exactly so native transitions remain compatible.
    for frame in range(end+1):
     phase=frame/at if frame<=at else (end-frame)/max(1,end-at)
     envelope=math.sin(math.pi*.5*max(0.,min(1.,phase)))**2
     sign=1 if part=='right_foot'else -1
     if bone==ankle:offset=(axis[0]*envelope,axis[1]*sign*envelope,axis[2]*sign*envelope)
     elif bone=='middle':offset=(.065*envelope,.025*sign*envelope,(-.10 if style=='outside'else .075)*sign*envelope)
     else:offset=(.055*envelope,(-1 if bone=='left_shoulder'else 1)*.065*envelope,0.)
     q=qnormalize(qmul(exp(offset),sample(tracks[bone],frame,rotation=True)))
     values.extend([str(frame),*(f'{x:.8f}'for x in q)])
    lines.append(','.join(values))
   text='\n'.join(lines)+'\n'
   text+=f'<physical_technique>{style}</physical_technique>\n<generated_action>true</generated_action>\n'
   dest=ROOT/'data/media/animations/procedural_actions'/(relative.replace('/','_')[:-5]+'_'+style+'.anim')
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
   rows.append(dict(path=dest.relative_to(ROOT).as_posix(),source=relative,technique=style,foot=part,contact_frame=at,source_sha256=hashlib.sha256(raw).hexdigest()))
 (ROOT/'config/procedural-strikes.json').write_text(json.dumps(dict(generated_files=len(rows),new_captures=0,clips=rows),indent=2)+'\n')
 print(json.dumps(dict(generated_files=len(rows),new_captures=0)))
if __name__=='__main__':generate()
