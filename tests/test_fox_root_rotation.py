"""A Fox motion-root turn must rotate the whole rig without changing its pose."""
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_pes_action_bank import tracks, multiply

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('blender'),'Blender is required for the standalone retarget tool')
class FoxRootRotationTests(unittest.TestCase):
    def test_separate_root_yaw_is_applied_once_to_the_pelvis_and_not_to_relative_limbs(self):
        bones=[]
        def add(name,parent,pos):
            bones.append(dict(name=name,parent=parent,pos=pos,rot=[0,0,0,1]));return len(bones)-1
        add('sk_root_hip',-1,[0,.96,0]);add('sk_chest',0,[0,.15,0]);add('sk_head',1,[0,.5,.03])
        for side,x in [('l',.16),('r',-.16)]:
            upper=add('sk_upperarm_'+side,1,[x,.48,.01])
            lower=add('sk_forearm_'+side,upper,[0,-.33,0]);add('sk_hand_'+side,lower,[0,-.25,0])
        for side,x in [('l',.087),('r',-.087)]:
            thigh=add('sk_thigh_'+side,0,[x,-.01,0])
            leg=add('sk_leg_'+side,thigh,[0,-.42,0]);add('sk_foot_'+side,leg,[0,-.44,.04])
        clip=dict(name='synthetic_root_turn',frames=4,fps=30,tracks={},
                  root=dict(pos=[[0,0,0,0],[4,0,0,0]],rot=[[0,0,0,0,1],[4,0,math.sqrt(.5),0,math.sqrt(.5)]]))
        with tempfile.TemporaryDirectory()as tmp:
            tmp=Path(tmp);(tmp/'rig.json').write_text(json.dumps(dict(bones=bones)))
            (tmp/'clip.json').write_text(json.dumps(clip))
            process=subprocess.run(['blender','-b','--python',str(ROOT/'tools/animations/retarget_fox_clip.py'),'--',
                                    str(tmp/'clip.json'),str(tmp/'rig.json'),str(tmp/'turn.anim')],capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            self.assertTrue((tmp/'turn.anim').is_file(),process.stdout+process.stderr)
            pose=tracks((tmp/'turn.anim').read_text());first=pose['body'][0][1:];last=pose['body'][-1][1:]
            delta=multiply(last,(-first[0],-first[1],-first[2],first[3]))
            angle=math.radians(90)*pose['body'][-1][0]*.01*30/4
            expected=(0,0,math.sin(angle*.5),math.cos(angle*.5))
            self.assertGreater(abs(sum(x*y for x,y in zip(delta,expected))),.999999)
            for name,keys in pose.items():
                if name in ['player','body']:continue
                a,b=keys[0][1:],keys[-1][1:]
                self.assertGreater(abs(sum(x*y for x,y in zip(a,b))),.999999,name)


if __name__=='__main__':unittest.main()
