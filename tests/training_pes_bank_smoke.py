"""Validate automatic PES-bank selection, physical contact and native fallback.

The report distinguishes actual PES contacts from native fallback. A decoded
or baked file alone is not counted as a successfully exercised game action.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from native_training_harness import NativeTraining
from training_pes_shortpass_smoke import events


def skeleton_metrics(log,pes,actor):
    joints=events(log,'TRAINING_CONTACT_JOINTS')
    states=[r for r in events(log,'NATIVE_APPROVED_SELECT')if r.get('actor')==actor]
    end=max((int(r['t'])for r in joints),default=0)
    intervals=[(int(r['t']),int(states[i+1]['t'])+160 if i+1<len(states)else end)
               for i,r in enumerate(states)if r.get('source','').startswith('pes17/')]
    intervals += [(int(r['t']),int(r['t'])+int(r['frames'])*10)for r in events(log,'PES_POSE_TRANSITION')if r.get('actor')==actor]
    upper=any(r.get('upper_layer')=='1'for r in pes)
    all_rates=[];pes_rates=[];finite=True
    for r in joints:
        for key in r:
            if key.startswith('j'):
                q=[float(v)for v in r[key].strip('[]').split(',')]
                finite&=all(math.isfinite(v)for v in q)and abs(sum(v*v for v in q)-1)<.00003
    for previous,current in zip(joints,joints[1:]):
        dt=(int(current['t'])-int(previous['t']))*.001
        if not 0<dt<=.08:continue
        full=any(start<=int(current['t'])<=finish or start<=int(previous['t'])<=finish for start,finish in intervals)
        for key in previous:
            if not key.startswith('j'):continue
            u=[float(x)for x in previous[key].strip('[]').split(',')]
            v=[float(x)for x in current[key].strip('[]').split(',')]
            dot=sum(x*y for x,y in zip(u,v))/math.sqrt(sum(x*x for x in u)*sum(x*x for x in v))
            rate=2*math.acos(min(1,abs(dot)))/dt;all_rates.append(rate)
            # Full-body clips own the legs. The approved native legs remain
            # independent during a torso-only reception. Preserve that
            # distinction instead of attributing native gait rates to PES.
            if full or (upper and key=='j1'):pes_rates.append(rate)
    return dict(finite=finite,samples=len(joints),pes_intervals=len(pes_rates),
                peak_pes_joint_speed_rad_s=max(pes_rates,default=0),
                peak_all_joint_speed_rad_s=max(all_rates,default=0),
                scope='Full PES clips plus 160 ms exit; torso only for upper reception; native fallback rates recorded separately.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--display',default=':3990')
    p.add_argument('--camera',type=int,choices=[1,2],default=1)
    a=p.parse_args()
    bank=Path(__file__).resolve().parents[1]/'data/media/training/pes17'
    catalog=json.loads((bank/'catalog.json').read_text())
    report=dict(result='running',checks=[],scenarios={},
                executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest(),
                bank_catalog_sha256=hashlib.sha256((bank/'catalog.json').read_bytes()).hexdigest(),
                source_clips=catalog['source_clips'],runtime_candidates=catalog['runtime_candidates'],
                scope='Rendered Linux/SDL Xbox input. Automatic hybrid selection; original PES selector, timing and physics not recovered.')

    def check(name,ok,evidence):
        row=dict(check=name,result='passed'if ok else'failed',evidence=evidence)
        report['checks'].append(row);print(json.dumps(row),flush=True)

    # A few arrivals deliberately exercise fallback: their trajectory need
    # not fit a curated PES clip. All commands still need an actual contact.
    scenarios=[
        ('forward_pass',1,120,0,0,None,[],4,True),
        ('left_pass',1,120,45,0,None,[],4,True),
        ('right_pass',1,120,-45,0,None,[],4,True),
        ('lateral_pass',1,120,90,0,None,[],4,True),
        ('strong_pass',1,750,0,0,None,[],4,False),
        ('weak_shot',4,50,0,0,None,[],8,False),
        ('instep_shot',4,500,0,0,None,[],8,True),
        ('diagonal_shot',4,400,45,0,None,[],8,False),
        ('cross',2,300,0,0,None,[],6,True),
        ('diagonal_cross',2,300,45,0,None,[],6,False),
        ('central_receive',0,0,0,0,'F4',['z'],None,False),
        ('instep_receive',0,0,0,0,'F5',['7'],None,True),
        ('thigh_receive',0,0,0,0,'F5',['8'],None,True),
        ('chest_receive',0,0,0,0,'F5',[],None,True),
        ('jumping_header',4,300,0,0,'F6',['Shift_L'],8,True),
        # A gait-phase-dependent native fallback is a valid physical action.
        # The combined two-view suite still requires actual PES running-pass
        # and running-shot contacts, in addition to the five action families.
        ('running_pass',1,180,0,900,None,[],4,False),
        # The source depends on the exact gait phase at release. Keep the
        # native shot when its shoe is the reachable one; the release suite
        # additionally requires a real contact from the PES running shot
        # across the two views.
        ('running_shot',4,300,0,900,None,[],8,False),
        ('running_cross',2,300,0,900,None,[],6,False),
    ]
    try:
        with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=a.camera,
                            config_overrides=dict(context_x=640,context_y=360,training_physical_lab='true',
                                                  training_motion_diagnostics='true'if a.camera==2 else'false'),
                            extra_arguments=['--pes-actions'])as g:
            def pad(angle,**kw):
                x,y=-math.sin(math.radians(angle)),-math.cos(math.radians(angle))
                g.pad(*((-y,x)if a.camera==1 else(x,y)),**kw)

            loaded=events(g.read_log(),'PES_ACTION_CANDIDATE')
            unique={r['name']:r for r in loaded}
            check('the complete curated bank loads with native fallbacks retained',
                  len(unique)==catalog['runtime_candidates']and all(r.get('native_bank_preserved')=='1'for r in unique.values()),
                  dict(expected=catalog['runtime_candidates'],loaded=len(unique)))
            pairs=[]
            for name,row in unique.items():
                if '_mirror'not in name:continue
                original=unique[name.replace('_mirror','')]
                pairs.append(row.get('contact')==original.get('contact')and row['frames']==original['frames'])
            check('mirrored candidates own independent event maps with identical timing',bool(pairs)and all(pairs),dict(pairs=len(pairs)))
            g.reset();start=len(g.read_log());pad(0);g.advance(1800);g.pad(0,0);g.advance(300)
            log=g.read_log()[start:]
            check('owned forward dribbling completes actual control touches without triggering a receiving trap',
                  any(r.get('function')=='2'for r in events(log,'TRAINING_ACTION_TOUCH'))and
                  all(r.get('function')=='2'for r in events(log,'PES_ACTION_CONTACT')),events(log,'TRAINING_NATIVE_START'))
            observed=set()
            for name,button,hold,angle,run,key,mods,function,require_pes in scenarios:
                g.reset();start=len(g.read_log());start_time=g.frames()[-1]['t']
                if run:pad(0,sprint=True);g.advance(run)
                if key:
                    g.keys([*mods,key],True);g.advance(100);g.keys([*mods,key],False)
                if button:
                    if run:pad(0,buttons=button,sprint=True)
                    else:g.pad(0,0,buttons=button)
                    g.advance(max(10,hold-30))
                    if angle:pad(angle,buttons=button,sprint=bool(run))
                    g.advance(30)
                    if angle or run:
                        pad(angle,sprint=bool(run));g.advance(100)
                    g.pad(0,0)
                for _ in range(45):
                    g.advance(50)
                    hits=events(g.read_log()[start:],'TRAINING_ACTION_TOUCH')
                    if any(function is None or r.get('function')==str(function)for r in hits):break
                if name in {'instep_shot','cross','thigh_receive','chest_receive','jumping_header','running_shot'}:
                    subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
                g.advance(1200)
                log=g.read_log()[start:]
                hits=[r for r in events(log,'TRAINING_ACTION_TOUCH')if function is None or r.get('function')==str(function)]
                pes=[r for r in events(log,'PES_ACTION_CONTACT')if function is None or r.get('function')==str(function)]
                observed.update(r['name']for r in pes)
                row=dict(start_ms=start_time,end_ms=g.frames()[-1]['t'],contacts=hits,pes_contacts=pes,native_sources=events(log,'TRAINING_NATIVE_START'))
                report['scenarios'][name]=row
                check(name+' completes the requested real-ball action',bool(hits)and(bool(pes)or not require_pes),row)
                skin=events(log,'TRAINING_SKIN_CONTACT')
                matched=[]
                for hit in pes:
                    part='chest'if hit.get('upper_layer')=='1'else hit['part']
                    matched.append(any(r['t']==hit['t']and r.get('part')==part and r.get('accepted')=='1'
                                       and float(r['gap'])<=.00251 for r in skin))
                check(name+' never substitutes an annotation for actual skin contact',all(matched),dict(pes_contacts=len(pes),matched_skin_contacts=sum(matched)))
                metrics=skeleton_metrics(log,pes,(pes or hits or[dict(actor='10')])[0]['actor'])
                check(name+' keeps the rendered skeleton finite through transitions',metrics['finite']and metrics['samples']>10 and metrics['peak_pes_joint_speed_rad_s']<40,metrics)
                if any(r.get('upper_layer')=='1'for r in pes):
                    masks=events(log,'TRAINING_UPPER_MASK')
                    check(name+' leaves the approved leg and root motion independent of the torso layer',bool(masks)and
                          max(float(r['legs_error'])for r in masks)<.0001 and max(float(r['root_error'])for r in masks)<.0001,
                          dict(samples=len(masks),maximum_leg_error=max((float(r['legs_error'])for r in masks),default=999)))
                if a.camera==2:
                    eyes=events(log,'FIRSTPERSON_FRAME')
                    check(name+' keeps the first-person lens on the rendered head',bool(eyes)and
                          max(float(r['anchor_error'])for r in eyes)<.025 and
                          min(float(r['alignment'])for r in eyes)>.999,
                          dict(samples=len(eyes),maximum_anchor_error=max((float(r['anchor_error'])for r in eyes),default=999),
                               minimum_alignment=min((float(r['alignment'])for r in eyes),default=0)))
                before=g.frames()[-1]['player'];pad(0);frames=g.advance(900);g.pad(0,0)
                distance=math.dist(before[:2],frames[-1]['player'][:2])
                check(name+' returns control to the approved locomotion',distance>.25,dict(distance_m=distance))
            check('actual contacts exercise multiple distinct source movements',len(observed)>=8,sorted(observed))
            learned=events(g.read_log(),'PES_LEARNED_MATCH')
            if catalog['source_clips']>21:
                check('the trained metric participates in actual runtime selection',
                      bool(learned)and all(math.isfinite(float(r['cost']))for r in learned),dict(decisions=len(learned)))
            report['observed_source_clips']=sorted(observed)
            if a.camera==2:
                eyes=events(g.read_log(),'PHYSICAL_EYE')
                check('the lens stays outside the rendered torso during the new actions',bool(eyes)and
                      all(float(r['clearance'])>=float(r['required'])-.0005 for r in eyes),dict(samples=len(eyes)))
            # Compare mode must restore native actions without unloading the bank.
            g.keys(['Insert'],True);g.advance(100);g.keys(['Insert'],False);g.advance(100)
            g.reset();start=len(g.read_log());g.pad(0,0,buttons=4);g.advance(300);g.pad(0,0);g.advance(2200)
            log=g.read_log()[start:]
            check('Insert restores the original action bank',not events(log,'PES_ACTION_CONTACT')and
                  any(r.get('function')=='8'for r in events(log,'TRAINING_ACTION_TOUCH')),events(log,'TRAINING_NATIVE_START'))
            g.keys(['Escape'],True);g.game.wait(timeout=15)
            check('clean exit',g.game.returncode==0,g.game.returncode)
    except Exception as error:
        check('rendered bank session completes',False,repr(error))
    check('the animation bank did not change during validation',
          hashlib.sha256((bank/'catalog.json').read_bytes()).hexdigest()==report['bank_catalog_sha256'],report['bank_catalog_sha256'])
    report['result']='passed'if all(r['result']=='passed'for r in report['checks'])else'failed'
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if report['result']=='passed'else 1)


if __name__=='__main__':main()
