"""Registered sprite extraction and baked two-bone IK for Spine 4.3.

The backing layer was reconstructed with imagegen. All moving arm artwork comes
from the supplied sheet. No whole-image scaling, pouring effects or physics.
"""
import math
import os
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from spine_rig import (Rig, Sheet, trim, place, centered, write_outputs,
                       write_skeleton, remap_alpha, draw_attachment, rot, attach)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
OUT = os.path.join(REPO, 'character-spine-preview/assets')
DEBUG = os.path.join(os.path.dirname(__file__), '_debug/reveler')
SRC = os.path.join(REPO, 'ChatGPT Image Sep 15, 2026, 09_13_25 AM.png')
SCALE = 1.30
SH = np.array([613., 270.])
SRC_SH = np.array([735., 1010.])
SRC_EL = np.array([785., 927.])
SRC_WR = np.array([748., 834.])
L1 = np.linalg.norm(SRC_EL-SRC_SH)*SCALE
L2 = np.linalg.norm(SRC_WR-SRC_EL)*SCALE
REST_WR = np.array([786., 300.])
ORIGIN = (510, 710)

def angle(v):
    return math.degrees(math.atan2(-v[1], v[0]))

def ik(wrist):
    v = np.asarray(wrist)-SH
    d = np.linalg.norm(v)
    a = (L1*L1-L2*L2+d*d)/(2*d)
    h = math.sqrt(max(0,L1*L1-a*a))
    elbow = SH + a*v/d + h*np.array([-v[1],v[0]])/d
    return elbow, angle(elbow-SH), angle(np.asarray(wrist)-elbow)

REST_EL, A0, B0 = ik(REST_WR)
AS = angle(SRC_EL-SRC_SH)
BS = angle(SRC_WR-SRC_EL)

def cut_poly(source, name, points):
    mask = Image.new('L', (source.shape[1],source.shape[0]))
    ImageDraw.Draw(mask).polygon(points, fill=255)
    a=source.copy()
    a[:,:,3] = (a[:,:,3].astype(float)*np.asarray(mask)/255).astype('uint8')
    return trim(name,a,0,0)

def backing():
    a=np.array(Image.open(os.path.join(OUT,'body-backing-source.png')).convert('RGBA'))
    # Technical matte extraction: generated checkerboard is neutral, unlike art.
    rgb=a[:,:,:3].astype(float)
    neutral=(rgb.max(2)-rgb.min(2)<13)&(rgb.min(2)>65)
    lab,n=ndimage.label(neutral)
    sizes=np.bincount(lab.ravel())
    bg=neutral & (sizes[lab]>24)
    a[bg,3]=0
    return trim('body',a,0,0)

def interpolate(keys,t):
    for i in range(len(keys)-1):
        if t<=keys[i+1][0]+1e-8:
            ta,va=keys[i];tb,vb=keys[i+1]
            u=np.clip((t-ta)/(tb-ta),0,1)
            u=u*u*(3-2*u)
            return np.asarray(va)+(np.asarray(vb)-va)*u
    return np.asarray(keys[-1][1])

def motion(name):
    if name=='idle':
        return 4., [(0,[786,300,0]),(1,[793,295,-2]),(2,[786,291,0]),(3,[780,296,2]),(4,[786,300,0])]
    if name=='cheers':
        return 3.6,[(0,[786,300,0]),(.4,[802,319,-4]),(1.1,[806,164,-8]),(1.55,[815,160,-13]),(1.95,[806,173,-3]),(2.35,[811,161,-8]),(3.6,[786,300,0])]
    # Contact point is the left edge of the cup's rim in wrist-local space.
    # At the sip hold it coincides with lips (482,205).
    rim=np.array(rot(-75*SCALE,-91*SCALE,12))
    target=np.array([482.,205.])-rim
    return 4.8,[(0,[786,300,0]),(.45,[762,309,0]),(1.6,[*target,12]),(2.75,[*target,12]),(3.1,[target[0]+8,target[1]+6,6]),(4.8,[786,300,0])]

def face_keys(name,T):
    eyes=[(0,'eyes_open'),(T,'eyes_open')]
    mouth=[(0,'mouth_smile'),(T,'mouth_smile')]
    if name=='idle': eyes=[(0,'eyes_open'),(2.5,'eyes_closed'),(2.65,'eyes_open'),(T,'eyes_open')]
    if name=='cheers':
        eyes=[(0,'eyes_open'),(.9,'eyes_wink'),(2.7,'eyes_open'),(T,'eyes_open')]
        mouth=[(0,'mouth_smile'),(.8,'mouth_grin'),(2.8,'mouth_smile'),(T,'mouth_smile')]
    if name=='sip':
        eyes=[(0,'eyes_open'),(1.4,'eyes_closed'),(3.2,'eyes_open'),(T,'eyes_open')]
        mouth=[(0,'mouth_smile'),(1.3,'mouth_kiss'),(3.2,'mouth_smile'),(T,'mouth_smile')]
    return {'eyes':{'attachment':attach(*eyes)},'mouth':{'attachment':attach(*mouth)}}

def build():
    os.makedirs(DEBUG,exist_ok=True)
    S=Sheet(SRC)
    P={'body':backing()}
    arm=S.cut('arm',(624,699,192,345),floor=35,grow=2,min_inside=.7)
    full=np.zeros_like(S.rgba)
    full[arm.oy:arm.oy+arm.h,arm.ox:arm.ox+arm.w]=arm.rgba
    # Overlap the rounded elbow, and hide the wrist seam under the metal cuff.
    P['upper_arm']=cut_poly(full,'upper_arm',[(680,1080),(845,1080),(845,913),(800,901),(775,908),(753,936),(680,990)])
    P['forearm']=cut_poly(full,'forearm',[(718,837),(739,821),(774,825),(828,925),(800,951),(773,942),(759,919)])
    P['hand']=cut_poly(full,'hand',[(719,765),(738,772),(750,787),(767,824),(766,839),(740,849),(720,824),(711,812),(702,806),(704,793),(701,786),(708,779),(707,773)])
    P['cup']=S.cut('cup',(1218,275,135,145),floor=32,grow=2)
    boxes={'eyes_open':(540,72,188,98),'eyes_closed':(737,72,188,98),'eyes_wink':(930,72,185,98),'mouth_smile':(548,174,105,78),'mouth_grin':(675,171,123,84),'mouth_kiss':(1208,171,101,84)}
    for name,(x,y,w,h) in boxes.items():
        a=S.rgba[y:y+h,x:x+w].copy()
        a[:,:,3]=remap_alpha(a[:,:,3],24)
        # Feather the face-patch perimeter to avoid sticker-like skin seams.
        yy,xx=np.mgrid[:h,:w]
        fade=np.clip((1-((xx-w/2)/(w*.5))**2-((yy-h/2)/(h*.51))**2)*4,0,1)
        a[:,:,3]=(a[:,:,3]*fade).astype('uint8')
        P[name]=trim(name,a,x,y)
    R=Rig()
    R.bone('root',None,ORIGIN)
    R.bone('body','root',ORIGIN)
    R.bone('shoulder','body',SH,length=L1,rotation=A0)
    R.bone('elbow','shoulder',REST_EL,length=L2,rotation=B0)
    R.bone('wrist','elbow',REST_WR,length=58,rotation=0)
    R.bone('goblet','wrist',REST_WR,rotation=0)
    R.slot('body','body',{'body':centered(P['body'],P['body'].center_sheet,1)},'body')
    R.slot('upper_arm','shoulder',{'upper_arm':place(P['upper_arm'],SRC_SH,SH,SCALE,A0-AS)},'upper_arm')
    R.slot('forearm','elbow',{'forearm':place(P['forearm'],SRC_EL,REST_EL,SCALE,B0-BS)},'forearm')
    eyes={n:centered(P[n],(482,161),.63) for n in boxes if n.startswith('eyes')}
    mouths={n:centered(P[n],(482,205),.60 if n!='mouth_grin' else .52) for n in boxes if n.startswith('mouth')}
    R.slot('eyes','body',eyes,'eyes_open')
    R.slot('mouth','body',mouths,'mouth_smile')
    # Original plain goblet is registered to the gripping hand, not the body.
    cup_at=REST_WR+np.array([-37.,-40.])*SCALE
    R.slot('cup','goblet',{'cup':place(P['cup'],(1285,347),cup_at,SCALE*.82)},'cup')
    R.slot('hand','wrist',{'hand':place(P['hand'],SRC_WR,REST_WR,SCALE)},'hand')
    sk=write_skeleton(R,'articulated-reveler-v3',(),bounds=(-550,-750,1100,1500))
    sk['animations']={}
    for name in ['idle','cheers','sip']:
        T,keys=motion(name)
        bones={n:{'rotate':[]} for n in ['shoulder','elbow','wrist']}
        for t in np.linspace(0,T,round(T*60)+1):
            wx,wy,c=interpolate(keys,t)
            el,a,b=ik((wx,wy))
            vals=[a-A0,(b-a)-(B0-A0),c-(b-B0)]
            for n,val in zip(bones,vals):
                bones[n]['rotate'].append({'time':round(float(t),5),'value':round(float(val),5)})
        # Ensure identical start/end values for every keyed channel.
        for track in bones.values(): track['rotate'][-1]['value']=track['rotate'][0]['value']
        sk['animations'][name]={'bones':bones,'slots':face_keys(name,T)}
    write_outputs('wine_reveler',OUT,list(P.values()),sk)
    # Independent pose contact sheets, using the same FK transforms as the rig.
    for name,times in [('idle',[0,1,2,3]),('cheers',[0,1.1,1.95,3.6]),('sip',[0,.9,2,4.8])]:
        tiles=[]
        for t in times:
            T,keys=motion(name);wx,wy,c=interpolate(keys,t);el,a,b=ik((wx,wy))
            canvas=Image.new('RGBA',(1100,1500),(30,24,31,255))
            attachments=[centered(P['body'],P['body'].center_sheet,1),place(P['upper_arm'],SRC_SH,SH,SCALE,a-AS),place(P['forearm'],SRC_EL,el,SCALE,b-BS)]
            for slot,d in face_keys(name,T).items():
                att=d['attachment'][0]['name']
                for k in d['attachment']:
                    if k['time']<=t: att=k['name']
                attachments.append((eyes if slot=='eyes' else mouths)[att])
            cc=np.array([wx,wy])+np.array(rot(-37*SCALE,-40*SCALE,c))
            attachments.extend([place(P['cup'],(1285,347),cc,SCALE*.82,c),place(P['hand'],SRC_WR,(wx,wy),SCALE,c)])
            for att in attachments: canvas=draw_attachment(canvas,att,(0,0))
            canvas.save(os.path.join(DEBUG,f'{name}-{t}.png'))
            tiles.append(canvas.resize((330,450)))
        strip=Image.new('RGBA',(1320,450))
        for i,tile in enumerate(tiles): strip.alpha_composite(tile,(330*i,0))
        strip.save(os.path.join(DEBUG,f'{name}-poses.png'))
    with open(os.path.join(OUT,'rig-notes.json'),'w') as f:
        json.dump({'revision':3,'arm':'shoulder > elbow > wrist > goblet','backing':'imagegen reconstruction; source sheet arm and face attachments','loop':'All rotation timelines return exactly to setup; no physics','sipLip':[482,205]},f,indent=2)

if __name__=='__main__': build()
