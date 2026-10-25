"""Validate the retargeted source poses against the actual native bind and shoes."""
import hashlib,itertools,json,math,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def mul(a,b):
 x,y,z,w=a;u,v,s,t=b
 return (w*u+x*t+y*s-z*v,w*v-x*s+y*t+z*u,w*s+x*v-y*u+z*t,w*t-x*u-y*v-z*s)
def rotate(q,v):return mul(mul(q,(*v,0)),(-q[0],-q[1],-q[2],q[3]))[:3]
def add(a,b):return tuple(x+y for x,y in zip(a,b))
@unittest.skipUnless(any((ROOT/'data/media/animations/mocap').glob('*.anim')),
                     'Imported locomotion was explicitly removed from the approved native gameplay')
class MocapBank(unittest.TestCase):
 def test_native_support_and_loops(self):
  rig=json.loads((ROOT/'tools/animations/native_rig_reference.json').read_text())
  meta=json.loads((ROOT/'docs/mocap-retarget.json').read_text())
  self.assertEqual(meta['count'],10)
  parents=[-1,0,1,1,3,1,5,0,7,8,0,10,11]
  for clip in meta['clips']:
   with self.subTest(source=clip['source_action']):
    file=ROOT/'data/media/animations/mocap'/(clip['export_name']+'.anim');raw=file.read_bytes()
    self.assertEqual(hashlib.sha256(raw).hexdigest(),clip['output_sha256'])
    tracks={x.split(',')[0]:x.split(',')[1:]for x in raw.decode().splitlines()if ','in x and not x.startswith('<')}
    self.assertIn('<type>movement</type>',raw.decode());self.assertIn('<touchframe>-1</touchframe>',raw.decode())
    root=tracks['player'];count=len(root)//4;self.assertEqual(count,clip['samples'])
    self.assertTrue(clip['hinge_frames_from_bend_planes'])
    velocity=[tuple((float(root[(i+1)*4+1+c])-float(root[i*4+1+c]))*100 for c in range(2))for i in range(count-1)]
    self.assertLess(max(math.dist(velocity[0],v)for v in velocity),.0001)
    poses=[]
    for bone in rig['bones']:
     values=tracks[bone['name']];self.assertEqual(len(values),count*5)
     quats=[tuple(float(v)for v in values[i+1:i+5])for i in range(0,len(values),5)]
     self.assertLess(max(abs(sum(v*v for v in q)-1)for q in quats),.00001)
     self.assertLess(1-abs(sum(a*b for a,b in zip(quats[0],quats[-1]))),.00001);poses.append(quats)
    for joint in [8,11,4,6]:
     lateral=max(2*math.asin(min(1,math.hypot(q[1],q[2])))for q in poses[joint])
     self.assertLess(lateral,.12,'knee/elbow axial roll would deform the skinned model')
     angles=[math.remainder(2*math.atan2(q[0],q[3]),2*math.pi)for q in poses[joint]]
     if joint in [8,11]:self.assertGreater(min(angles),-.12);self.assertLess(max(angles),2.8)
     else:self.assertGreater(min(angles),-2.8);self.assertLess(max(angles),.12)
    for frame in range(count):
     position=[(0,0,float(root[frame*4+3])+rig['bones'][0]['offset'][2])];rotation=[]
     for i,bone in enumerate(rig['bones']):
      rotation.append(mul(rotation[parents[i]],poses[i][frame])if i else poses[i][frame])
      if i:position.append(add(position[parents[i]],rotate(rotation[parents[i]],bone['offset'])))
     soles=[]
     for side,ankle in enumerate([9,12]):
      for bits in itertools.product([0,1],repeat=3):
       corner=[rig['feet'][side]['max'if bits[j]else'min'][j]for j in range(3)]
       soles.append(add(position[ankle],rotate(rotation[ankle],corner))[2])
     self.assertAlmostEqual(min(soles),.008,places=5)
     self.assertTrue(all(math.isfinite(v)for p in position for v in p))
     self.assertLess(max(math.dist(position[0],p)for p in position),1.2)
if __name__=='__main__':unittest.main()
