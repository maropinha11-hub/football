"""Fetch primary active-character-control references for the research log."""
import concurrent.futures,hashlib,json,urllib.request
from pathlib import Path
sources={
 'deepmimic_project':'https://xbpeng.github.io/projects/DeepMimic/',
 'deepmimic_readme':'https://raw.githubusercontent.com/xbpeng/DeepMimic/master/README.md',
 'deepmimic_license':'https://raw.githubusercontent.com/xbpeng/DeepMimic/master/LICENSE',
 'amp_project':'https://xbpeng.github.io/projects/AMP/',
 'amp_readme':'https://raw.githubusercontent.com/isaac-sim/IsaacGymEnvs/main/README.md',
 'spring_damping':'https://theorangeduck.com/page/spring-roll-call'}
out=Path('/workspace/.football-active-control-research');out.mkdir(exist_ok=True)
def fetch(item):
 name,url=item
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Football research'}),timeout=20)as response:data=response.read(1500000);status=response.status
  (out/(name+'.txt')).write_bytes(data)
  return dict(name=name,url=url,status=status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 except Exception as error:return dict(name=name,url=url,error=str(error))
rows=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(fetch,sources.items()))
(out/'sources.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
