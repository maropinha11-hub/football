"""Conservative native action contexts from the decoded motion names.

Names provide weak family labels, not recovered PES event/state metadata.
Unknown and presentation-only clips never acquire an invented gameplay action.
"""
import re

def describe(name):
    if not name:return None
    family=name.split('_')[0]
    direction=re.findall(r'(?:^|_)(f?\d{3})(?=_|$)',name)
    angle=direction[0] if direction else '000'
    yaw=-int(angle[1:]) if angle.startswith('f') else int(angle)
    height=re.search(r'(?:^|_)y(\d+)(?:_|$)',name)
    level=int(height[1]) if height else 0
    intervals=[(.08,.36),(.15,.56),(.32,.82),(.48,1.02),(.65,1.25),
               (.85,1.5),(1.05,1.85),(1.25,2.3),(1.55,2.7),(1.8,3.1),(1.9,3.2),(2.1,3.4)]
    band=list(intervals[min(level,11)])
    motion=re.search(r'(?:^|_)([0-4])_([0-4])(?:_|$)',name)
    incoming=int(motion[1])if motion else 0
    speed=[0,2.2]if incoming==0 else[0,4]if incoming==1 else[.6,7]if incoming==2 else[1.4,10]
    row=dict(direction=yaw,height=band,speed=speed,root_motion=True,body_support=True,
             max_ball_speed=28,power=[0,1],part='right_foot',mirror=abs(yaw)>1)
    if family=='kick':
        distance=name.split('_')[1]
        if distance not in ['short','mid','long']:return None
        row.update(action={'short':'shortpass','mid':'highpass','long':'shot'}[distance],
                   role={'short':'pass','mid':'cross','long':'shot'}[distance],infer_contact=True,infer_foot=True)
        for token,technique in [('heel','heel'),('outside','outside'),('out','outside'),('inside','inside'),('infront','instep'),('instep','instep')]:
            if token in name.split('_'):row['technique']=technique;break
    elif family=='head':
        row.update(action='shortpass',role='header',part='head',infer_contact=True)
        row['height']=[max(.5,band[0]-.2),max(1.35,band[1])]
    elif family in ['trap','traprun','trapback','trapside']:
        part='head'if '_head' in name else'trunk'if any(t in name for t in ['breast','belly'])else'right_upperleg'if 'thigh'in name else'right_foot'
        row.update(action='trap',role='reception',part=part,infer_contact=True,infer_foot=part.endswith('foot'))
        if part=='trunk':row['height']=[.85,1.75]
        if part=='head':row['height']=[1.4,2.8]
    elif family in ['dribble','dribblerun','dribbleslide000','dribbleslide045','dribbleslide090','dribbleslide180','feint','feintrun','feintslide045','feintslide090','feintback']:
        if 'loop'in name:return None
        row.update(action='ballcontrol',role='control',infer_contact=True,infer_foot=True)
        if not height:row['height']=[.08,.45]
    elif family=='tacklefoot':
        row.update(action='interfere',role='tackle',infer_contact=True,infer_foot=True,height=[.08,.65])
    elif family in ['sliding','slidingkeep']:
        row.update(action='sliding',role='tackle',infer_contact=True,infer_foot=True,height=[.08,.65])
    elif family in ['fall','stagger','lose','tackleshoulder','tacklepulled','dodge','avoidjump','avoidslide','gkstagger','gkfall','goalpost','goalnet']:
        row.update(action='trip',role='balance',trip_type=2 if family=='fall'else 1,height=[0,4],speed=[0,12])
    elif family in ['riseup','gkrise']:
        row.update(action='movement',role='recovery',speed=[0,12],height=[0,4])
    elif family in ['run','runslant','runback','runparallel','runbackslant','heisou','jockey',
                    'walk','walkback','walkparallel','walkslant','walkbackslant','walkside',
                    'idle','side','back','backslant','parallel','mid','near','stand','rapidstop']:
        row.update(action='movement',role='locomotion',height=[0,4])
    elif family.startswith('gkmove')or family in ['gkprejump','gksavingCancel','gkseeoff','gkcoaching','gkdeflectExpect','gkdeflectExpect3','rapid']:
        row.update(action='movement',role='locomotion',height=[0,4],keeper_only=family.startswith('gk'))
    elif family in ['block','block090']:
        row.update(action='interfere',role='tackle',part='trunk',infer_contact=True,height=[.08,2.2],speed=[0,10])
    elif family in ['gkunderthrow','gkoverthrow','gksidethrow','gksidethrowcut']or(family=='throwin'and 'release'in name):
        if 'cancel'in name:return None
        row.update(action='highpass',role='cross',part='right_lowerarm',infer_contact=True,
                   height=[.3,2.8],speed=[0,5],retainer_in='right_elbow',mirror=True,
                   setpiece=family=='throwin',keeper_only=family.startswith('gk'))
    elif family=='gkclear'or(family=='gkgoalkick'and ('instep'in name or'inside'in name))or(family=='fk'and '_kick_'in name):
        row.update(action='highpass'if family.startswith('gk')else'shortpass',role='cross'if family.startswith('gk')else'pass',
                   infer_contact=True,infer_foot=True,height=[.08,.4],
                   setpiece=family in ['fk','gkgoalkick'],keeper_only=family.startswith('gk'))
    elif family.startswith('gk') and family in ['gkcatch','gkdeflect','gkdeflectscoop','gkpunch','gkblock','gkblockcover','gkcollapsing','gkdeflectlate','gkscoopout','gkpickupball']:
        row.update(action='deflect',role='keeper',part='right_lowerarm',infer_contact=True,
                   height=[.08,3.5],speed=[0,12],keeper_only=True)
        row['retain_ball']=family in ['gkcatch','gkpickupball']
    else:return None
    if family.startswith('gk'):row['keeper_only']=True
    return row
