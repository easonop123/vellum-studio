# Vellum Demo 01 v4 — cinematic 16:9 @24fps + vertical 9:16 wrap.  v4.py extract | masks | render a b | test f.. | audio | encode
import os, sys, math, random, subprocess, glob, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops
HOME=os.path.expanduser('~'); BASE=f"{HOME}/mnt/Downloads/Vellum Demo 01 - Tokyo Night"
NEWD=f"{BASE}/v4 clips"; FR=f"{HOME}/vellum/fr4"; OUT=f"{HOME}/vellum/out4"; OUTV=f"{HOME}/vellum/out4v"
A=f"{HOME}/mnt/WJC2026/Claude outputs/reel_assets"
W,H=1920,1080; FPS=24; BAR=1.89013; BEAT=BAR/4; DROP=3.8805-BAR   # song trimmed by 1 bar
def F(k): return int(round((DROP+k*BEAT)*FPS))
CL={}
for i,f in enumerate(sorted(x for x in os.listdir(NEWD) if x.endswith('.mp4')),1): CL[f'N{i:02d}']=f"{NEWD}/{f}"
for i,f in enumerate(sorted(x for x in os.listdir(BASE) if x.endswith('.mp4') and not x.startswith('Vellum')),1): CL[f'O{i:02d}']=f"{BASE}/{f}"
GRADE=("eq=contrast=1.10:saturation=1.14:gamma=0.97,"
       "colorbalance=rs=-0.07:gs=-0.01:bs=0.09:rm=-0.01:gm=0:bm=0.03:rh=0.09:gh=0.03:bh=-0.07,"
       "curves=all='0/0.035 0.25/0.22 0.75/0.79 1/0.97'")
RAWL="eq=saturation=0.62:contrast=0.82:brightness=0.035"
SEGS=[]
def seg(k0,k1,c,ss,sp=1.0,**kw):
    d=dict(k0=k0,k1=k1,f0=F(k0),f1=F(k1),c=c,ss=ss,sp=sp); d.update(kw); d['id']=f"s{len(SEGS):02d}"; SEGS.append(d); return d
# ---- intro: raw camera-roll clips on 8ths
RAWS=[('N01',10),('N21',3),('N13',5),('N06',2),('N16',4),('N02',1),('N20',4),('N34',12)]
for i,(c,ss) in enumerate(RAWS): seg(-4+i*0.5,-3.5+i*0.5,c,ss,1.0,raw=True,label=f"IMG_{4821+i*7}.MOV")
SEGS[0]['f0']=0
# ---- body
seg(0,4,'N28',3.2,0.5,interp=True,creep=.06,hero=True)
seg(4,5,'N01',6,0.8,tin='whip')
seg(5,6,'N08',7.6,0.7,punch=1)
seg(6,7,'N34',8,1.0)
seg(7,8,'N16',5,1.0,tin='whip')
seg(8,8.5,'N02',1.5,1.2,punch=1)
seg(8.5,9,'N29',2.6,1.2)
seg(9,10,'N29',5.0,0.8,bw=3)
seg(10,12,'N11',6.6,0.5,tin='burn',creep=.05)
seg(12,13,'N27',4,1.0,punch=1)
seg(13,14,'N10',3,1.0,tin='whip')
seg(14,16,'N21',12,0.7,creep=.05)
seg(16,17,'N13',8,1.0,punch=1,white=1)
seg(17,18,'O19',2,0.6)
seg(18,19,'N35',3,1.0,fy=.35,punch=1)
seg(19,20,'N26',4,1.0,fy=.3,tin='whip')
for i,(c,ss) in enumerate([('N16',9),('N34',14),('N08',12),('N01',14),('N21',40),('N13',14),('N20',8),('N29',6.5)]):
    seg(20+i*0.5,20.5+i*0.5,c,ss,1.0,punch=1,bw=(3 if i%2 else 0))
seg(24,26,'N20',5,1.0,tin='whip',white=1)
seg(26,28,'N28',9,0.8,tin='dissolve',creep=.04)
seg(28,30,'N19',1,1.0,creep=.05)
seg(30,31,'N02',3,1.0,punch=1)
seg(31,32,'N09',4,1.0,tin='whip')
for i,(c,ss) in enumerate([('N13',3),('N01',20),('N16',2),('N34',3),('N08',3),('N21',60),('O12',5),('N29',1)]):
    seg(32+i*0.25,32.25+i*0.25,c,ss,1.0,punch=1)
seg(34,36,'N01',24,(0.6,3.0),zt=5)
seg(36,40,'O19',5,0.4,creep=.08,boom=1,leak=(F(38)-F(36),9))
seg(40,42,'N34',14,0.8,tin='burn')
seg(42,43,'N16',11,1.0,tin='whip')
seg(43,44,'N08',20,1.0,tin='whip')
seg(44,48,'O24',2,0.7,creep=.06,ending=1)
END=F(48); TOTAL=F(52)
# ---------------------------------------------------------------- probe / extract
_pc={}
def probe(p):
    if p in _pc: return _pc[p]
    o=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',p],stdin=subprocess.DEVNULL))['streams'][0]
    a,b=o['r_frame_rate'].split('/'); _pc[p]=(o['width'],o['height'],float(a)/float(b)); return _pc[p]
def spd(sp,i,n):
    if isinstance(sp,(tuple,list)): p=i/max(1,n-1); return sp[0]+(sp[1]-sp[0])*p*p
    return sp
def srcfps(s):
    f=probe(CL[s['c']])[2]; return f*2 if s.get('interp') else f
def cum(s):
    n=s['f1']-s['f0']+16; L=[]; acc=0.0; sf=srcfps(s)
    for j in range(n): L.append(acc); acc+=spd(s['sp'],min(j,s['f1']-s['f0']-1),s['f1']-s['f0'])*sf/FPS
    return L,int(math.ceil(acc))+3
def cropflt(s):
    w,h,_=probe(CL[s['c']]); a=W/H
    if w/h>a: cw=int(h*a)//2*2; x=int((w-cw)*s.get('fx',0.5))//2*2; return f"crop={cw}:{h}:{x}:0"
    ch=int(w/a)//2*2; y=int((h-ch)*s.get('fy',0.45))//2*2; return f"crop={w}:{ch}:0:{y}"
def extract(s):
    d=f"{FR}/{s['id']}"; os.makedirs(d,exist_ok=True)
    _,n=cum(s)
    if len(glob.glob(d+'/*.jpg'))>=n-2: return
    vf=[]
    if s.get('interp'): vf.append(f"minterpolate=fps={probe(CL[s['c']])[2]*2}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
    vf+= [cropflt(s), f"scale={W}:{H}:flags=lanczos", RAWL if s.get('raw') else GRADE]
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(s['ss']),'-i',CL[s['c']],'-vf',','.join(vf),'-frames:v',str(n),'-q:v','2',f"{d}/%04d.jpg"],check=True,stdin=subprocess.DEVNULL)
# ---------------------------------------------------------------- helpers
_fc={}; _cc={}
def sframe(s,i):
    sid=s['id']
    if sid not in _fc: _fc[sid]=sorted(glob.glob(f"{FR}/{sid}/*.jpg")); _cc[sid]=cum(s)[0]
    L=_cc[sid]; fs=_fc[sid]; j=int(L[max(0,min(i,len(L)-1))]); j=max(0,min(j,len(fs)-1))
    return Image.open(fs[j]).convert('RGB')
def font(p,s,var=None):
    f=ImageFont.truetype(p,s)
    if var:
        try: f.set_variation_by_name(var)
        except Exception: pass
    return f
FT=f"{HOME}/fonts"; ANTON=f"{FT}/Anton.ttf"; SG=f"{FT}/SpaceGrotesk.ttf"; JB=f"{FT}/JetBrainsMono.ttf"; ARCH=f"{FT}/ArchivoBlack.ttf"
RED=(214,24,32); BRED=(255,77,61); BONE=(237,234,228); GREY=(150,146,140); BLACK=(10,10,12)
def scale_c(im,s,cx=0.5,cy=0.5):
    if abs(s-1)<1e-3: return im
    w,h=im.size; nw,nh=int(w*s),int(h*s); b=im.resize((nw,nh),Image.BILINEAR); x=int((nw-w)*cx); y=int((nh-h)*cy); return b.crop((x,y,x+w,y+h))
def zoomblur(im,amt,n=8):
    sm=im.resize((960,540)); acc=np.zeros((540,960,3),np.float32)
    for j in range(n): acc+=np.asarray(scale_c(sm,1+amt*0.28*j/(n-1)),np.float32)
    return Image.fromarray((acc/n).astype(np.uint8)).resize((W,H),Image.BILINEAR)
def mblur(im,px,n=14):
    sm=im.resize((960,540)); a=np.asarray(sm,np.float32); acc=np.zeros_like(a); p=px/2
    for j in range(n): acc+=np.roll(a,int(p*(j/(n-1)-0.5)),1)
    return Image.fromarray((acc/n).astype(np.uint8)).resize((W,H),Image.BILINEAR)
def shake(im,amp,split,seed):
    r=random.Random(seed); a=np.asarray(im); dx=int(r.uniform(-1,1)*amp); dy=int(r.uniform(-1,1)*amp); a=np.roll(a,(dy,dx),(0,1)).copy()
    if split>=1: s=int(split); a[:,:,0]=np.roll(a[:,:,0],s,1); a[:,:,2]=np.roll(a[:,:,2],-s,1)
    return Image.fromarray(a)
_X=np.linspace(0,1,W)[None,:]; _Y=np.linspace(0,1,H)[:,None]
def burn(im,p,cx=None):
    cx=-0.2+1.4*p if cx is None else cx
    g=np.exp(-(((_X-cx)/0.45)**2+((_Y-0.5)/0.8)**2))*min(1,2.2*math.sin(math.pi*min(1,p))+0.2)
    col=np.stack([255*g,150*g,70*g],-1)
    a=np.asarray(im,np.float32); a=255-(255-a)*(255-col)/255; return Image.fromarray(np.clip(a,0,255).astype(np.uint8))
def bw(im): return ImageOps.grayscale(im).convert('RGB')
def ease(p): p=max(0,min(1,p)); return p*p*(3-2*p)
VIG=None; GRAIN=[]
def finish(im,f):
    global VIG
    if VIG is None:
        r=np.sqrt(((_X-0.5)/0.62)**2+((_Y-0.5)/0.62)**2); VIG=np.clip(1-0.38*np.clip(r-0.55,0,1)**1.6*2.2,0.55,1)[...,None].astype(np.float32)
        rng=np.random.default_rng(3)
        for _ in range(6): GRAIN.append(np.asarray(Image.fromarray(((rng.normal(0,1,(540,960))*9)+128).clip(0,255).astype(np.uint8)).resize((W,H),Image.BILINEAR),np.float32)-128)
    a=np.asarray(im,np.float32)
    sm=np.asarray(im.resize((480,270)),np.float32); hi=np.clip((sm.max(2,keepdims=True)-170)/85,0,1)*sm
    bl=np.asarray(Image.fromarray(hi.astype(np.uint8)).filter(ImageFilter.GaussianBlur(9)).resize((W,H),Image.BILINEAR),np.float32)
    a=255-(255-a)*(255-bl*0.45)/255
    a=a*VIG+GRAIN[f%6][...,None]
    return Image.fromarray(np.clip(a,0,255).astype(np.uint8))
def fit_font(path,text,maxw,start=600):
    s=start
    while s>30:
        f=font(path,s)
        if f.getlength(text)<=maxw: return f
        s-=6
    return font(path,s)
# ---------------------------------------------------------------- hero title behind subject
MASKD=f"{HOME}/vellum/mask4"
def hero_mask(s,i):
    p=f"{MASKD}/{s['id']}_{i:04d}.png"
    return Image.open(p).convert('L') if os.path.exists(p) else None
FT_T=None
def hero(im,s,i):
    global FT_T
    if FT_T is None: FT_T=fit_font(ANTON,"TOKYO",W*0.88)
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    txt="TOKYO"; n=min(5,max(0,(i-2)//2+1)) if i>=2 else 0
    tw=FT_T.getlength(txt); bb=FT_T.getbbox(txt); x0=(W-tw)/2; y0=H*0.40-(bb[3]-bb[1])/2-bb[1]
    # draw full-width layout but only first n letters
    d.text((x0,y0),txt[:n],font=FT_T,fill=RED+(255,))
    fs=font(ANTON,150); ys=y0+bb[3]+18
    if i>=14: d.text((x0+12,ys),"AFTER",font=fs,fill=RED+(255,))
    if i>=18: w2=fs.getlength("DARK"); d.text((x0+tw-w2-12,ys),"DARK",font=fs,fill=RED+(255,))
    out=Image.alpha_composite(im.convert('RGBA'),lay).convert('RGB')
    m=hero_mask(s,i)
    if m is not None: out.paste(im,(0,0),m)
    return out
# ---------------------------------------------------------------- render 16:9
def seg_at(f):
    for s in SEGS:
        if s['f0']<=f<s['f1']: return s
def base(s,i):
    im=sframe(s,i); n=s['f1']-s['f0']
    if s.get('creep'): im=scale_c(im,1+s['creep']*i/max(1,n))
    if s.get('punch') and i<4: im=scale_c(im,1+0.16*(1-i/4)**2)
    return im
F_L=font(JB,30,'Medium')
def render169(f):
    if f>=END: return endcard169(f)
    s=seg_at(f); i=f-s['f0']; n=s['f1']-s['f0']; k=SEGS.index(s)
    prev=SEGS[k-1] if k>0 else None; nxt=SEGS[k+1] if k+1<len(SEGS) else None
    im=base(s,i)
    if s.get('raw'):
        d=ImageDraw.Draw(im); d.text((40,H-70),s['label'],font=F_L,fill=(255,255,255))
        d.text((W-260,40),f"0:0{(i%24)//10}{i%10}",font=F_L,fill=(255,255,255))
        return im
    if s.get('hero'): im=hero(im,s,i)
    if s.get('bw') and i<s['bw']: im=bw(im)
    t=s.get('tin')
    if t=='whip' and i<3: im=mblur(im,[700,380,140][i])
    if nxt and nxt.get('tin')=='whip' and i>=n-3: im=mblur(im,[140,380,700][i-(n-3)])
    if t=='burn' and i<6: im=burn(im,0.45+i*0.1)
    if nxt and nxt.get('tin')=='burn' and i>=n-4: im=burn(im,(i-(n-4))*0.12+0.05)
    if t=='dissolve' and prev and i<8:
        pim=base(prev,prev['f1']-prev['f0']+i); im=ImageChops.screen(Image.blend(pim,Image.new('RGB',(W,H)),i/8),Image.blend(im,Image.new('RGB',(W,H)),max(0,1-i/8)*0.5))
    if s.get('zt') and i>=n-s['zt']: p=(i-(n-s['zt'])+1)/s['zt']; im=zoomblur(scale_c(im,1+0.9*p*p),0.7*p)
    if s.get('leak'):
        a,ln=s['leak']
        if a<=i<a+ln: im=burn(im,(i-a)/ln)
    if s.get('boom') or s.get('hero'):
        if i in (1,2): im=zoomblur(im,1.0 if i==1 else 0.5)
        if 1<=i<=10: im=shake(im,30*0.72**(i-1),6*(1-(i-1)/10),f)
    if s.get('ending'):
        b0=F(46)-s['f0']; d=ImageDraw.Draw(im)
        if i>=4:
            ft=font(ANTON,140); txt="TOKYO"; m=min(5,(i-4)//2+1); tw=ft.getlength(txt)
            ImageDraw.Draw(im).text(((W-tw)/2,H/2-110),txt[:m],font=ft,fill=BONE)
            if i>=14: f2=font(JB,34,'Medium'); s2="A F T E R   D A R K"; d.text(((W-f2.getlength(s2))/2,H/2+50),s2,font=f2,fill=BONE)
    im=finish(im,f)
    if s.get('ending'):
        b0=F(46)-s['f0']
        if i>=b0:
            p=ease((i-b0)/(n-b0)); bh=int(138+(H/2-138)*p**2.2)
        else: bh=int(138*min(1,(i+1)/6))
        d=ImageDraw.Draw(im); d.rectangle([0,0,W,bh],fill=(0,0,0)); d.rectangle([0,H-bh,W,H],fill=(0,0,0))
    whites={F(0),F(16),F(24),F(36)}
    if f in whites: im=Image.new('RGB',(W,H),(255,255,255))
    if f-1 in whites: im=Image.blend(im,Image.new('RGB',(W,H),(255,255,255)),0.45)
    return im
def endcard169(f):
    i=f-END; im=Image.new('RGB',(W,H),BLACK); d=ImageDraw.Draw(im)
    if (i//12)%2==0: d.ellipse([560,300,592,332],fill=BRED)
    d.text((610,296),f"00:00:{f//FPS:02d}:{f%FPS:02d}",font=font(JB,32,'Medium'),fill=GREY)
    d.text((550,340),"VELLUM"[:min(6,i//2+1)],font=font(SG,170,'Bold'),fill=BONE)
    if i>=8: d.text((560,540),"/ STUDIO",font=font(JB,44,'Medium'),fill=BRED)
    if i>=12: d.text((560,660),"send me your clips. i'll cut them to your song.",font=font(SG,40,'Medium'),fill=BONE)
    if i>=18: d.text((560,740),"DM TO BOOK  →  @vellumstudio.edits",font=font(JB,34,'Bold'),fill=BRED)
    if i==0: return Image.new('RGB',(W,H),(255,255,255))
    return im
# ---------------------------------------------------------------- vertical wrap
VW,VH=1080,1920; VY=656; VHt=608
F_BIG=font(SG,96,'Bold'); F_SM=font(JB,30,'Medium'); F_HUD=font(JB,30,'Bold'); F_CTA=font(SG,64,'Bold')
def ctext(d,y,t,fnt,fill): d.text(((VW-d.textlength(t,font=fnt))/2,y),t,font=fnt,fill=fill)
def wrapv(im169,f):
    if f>=END: return endcardv(f)
    v=Image.new('RGB',(VW,VH),(0,0,0)); v.paste(im169.resize((VW,VHt),Image.LANCZOS),(0,VY)); d=ImageDraw.Draw(v)
    if f<F(0):
        ctext(d,430,"your clips:",F_BIG,BONE); ctext(d,1310,"8 random clips · no edit",F_SM,GREY)
    elif f<F(44):
        ctext(d,370,"VELLUM STUDIO",F_SM,BRED); ctext(d,430,"my edit:",F_BIG,BONE)
    else:
        ctext(d,370,"VELLUM STUDIO",F_SM,BRED); ctext(d,430,"want yours like this?",font(SG,80,'Bold'),BONE)
    if f>=F(0):
        d.text((40,VY+VHt+30),"@vellumstudio.edits",font=F_SM,fill=GREY)
        e=f-F(0)
        if (e//12)%2==0: d.ellipse([VW-372,VY+VHt+38,VW-350,VY+VHt+60],fill=BRED)
        d.text((VW-338,VY+VHt+30),"REC",font=F_HUD,fill=BONE)
        d.text((VW-262,VY+VHt+32),f"00:00:{e//FPS:02d}:{e%FPS:02d}",font=font(JB,28,'Medium'),fill=BONE)
    if f>=F(40): ctext(d,1440,"DM me your clips →",F_CTA,BONE)
    return v
def endcardv(f):
    i=f-END; im=Image.new('RGB',(VW,VH),BLACK); d=ImageDraw.Draw(im)
    if (i//12)%2==0: d.ellipse([180,690,214,724],fill=BRED)
    d.text((232,686),f"00:00:{f//FPS:02d}:{f%FPS:02d}",font=font(JB,34,'Medium'),fill=GREY)
    d.text((170,740),"VELLUM"[:min(6,i//2+1)],font=font(SG,190,'Bold'),fill=BONE)
    if i>=8: d.text((178,960),"/ STUDIO",font=font(JB,48,'Medium'),fill=BRED)
    if i>=12: d.text((178,1160),"send me your clips.",font=font(SG,56,'Medium'),fill=BONE)
    if i>=15: d.text((178,1235),"i'll cut them to your song.",font=font(SG,56,'Medium'),fill=BONE)
    if i>=19: d.text((178,1350),"DM TO BOOK →",font=font(JB,40,'Bold'),fill=BRED)
    if i==0: return Image.new('RGB',(VW,VH),(255,255,255))
    return im
# ---------------------------------------------------------------- audio
def audio():
    SR=48000
    def load(p):
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',p,'-f','f32le','-ac','2','-ar',str(SR),'-'],stdin=subprocess.DEVNULL); return np.frombuffer(raw,np.float32).reshape(-1,2).copy()
    S={n:load(f"{A}/{n}.wav") for n in ['sfx16_click','sfx15_click_loud','sfx11_riser','sfx11_impact','sfx15_flash','sfx17_dslr','sfx11_whoosh','sfx17_phone','sfx13_shutterT','sfx17_ring']}
    N=int(TOTAL/FPS*SR); mix=np.zeros((N+SR,2),np.float32); rnd=random.Random(9); duck=[]
    def add(n,fr,db,fade=0.0):
        x=S[n]*(10**((db+rnd.uniform(-1.2,1.2))/20)); p=rnd.uniform(-.15,.15); x=x*np.array([1-p,1+p],np.float32)
        if fade: q=int(fade*SR); x[:q]*=np.linspace(0,1,q)[:,None]
        i=max(0,int(round(fr/FPS*SR))); j=min(len(mix),i+len(x)); mix[i:j]+=x[:j-i]
        if n=='sfx11_impact': duck.append((fr/FPS,-3.5))
        if n=='sfx15_flash': duck.append((fr/FPS,-1.5))
    for s in SEGS:
        f0=s['f0']; t=s.get('tin')
        if s.get('raw'): add('sfx16_click',f0,-9); continue
        if s.get('hero') or s.get('boom'):
            add('sfx11_riser',f0-48,-10,fade=0.8); add('sfx11_whoosh',f0-4,-6); add('sfx11_impact',f0,0); add('sfx15_flash',f0,-4); add('sfx15_click_loud',f0,-6)
            if s.get('hero'):
                for j in range(5): add('sfx16_click',f0+2+j*2,-8)
                add('sfx17_ring',f0+14,-12); add('sfx17_ring',f0+18,-13)
            continue
        if t=='whip': add('sfx11_whoosh',f0-3,-8); add('sfx17_phone',f0,-12)
        elif t=='burn': add('sfx11_whoosh',f0-4,-10); add('sfx15_flash',f0,-9)
        elif t=='dissolve': add('sfx11_whoosh',f0-2,-13)
        elif s['k1']-s['k0']<=0.25: add('sfx13_shutterT',f0,-9)
        elif s.get('punch'): add('sfx17_dslr',f0,-9)
        else: add('sfx16_click',f0,-11)
        if s.get('white'): add('sfx15_flash',f0,-6)
        if s.get('ending'):
            for j in range(5): add('sfx16_click',f0+4+j*2,-9)
            add('sfx17_ring',f0+18,-12)
    add('sfx15_flash',END,-5); add('sfx11_impact',END,-8); add('sfx17_ring',END,-12)
    for j in range(6): add('sfx16_click',END+j*2,-11)
    mix=mix[:N]; sfx=mix*(10**(6/20)); sfx=sfx/max(1,np.abs(sfx).max()/0.89); sfx.astype(np.float32).tofile('/tmp/sfx4.f32')
    song=load(f"{A}/song_wdim_v17c_m4.wav")[int(BAR*SR):][:N]; song=np.pad(song,((0,max(0,N-len(song))),(0,0)))
    env=np.ones(N,np.float32)
    for t0,db in duck:
        g=1-10**(db/20); lo=int(t0*SR); hi=min(N,lo+int(0.3*SR)); tt=np.arange(hi-lo)/SR
        env[lo:hi]-=g*np.clip(tt/0.006,0,1)*np.clip(1-(tt-0.035)/0.22,0,1)
    song*=np.clip(env,0.3,1)[:,None]*10**(-2/20); q=int(0.5*SR); song[-q:]*=np.linspace(1,0,q)[:,None]
    pv=song+mix; pv=pv/max(1,np.abs(pv).max()/0.89); pv.astype(np.float32).tofile('/tmp/pv4.f32'); print('audio ok')
def encode():
    enc=['-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-r',str(FPS)]
    af=lambda p:['-f','f32le','-ar','48000','-ac','2','-i',p]; nm="Vellum Demo 01 - Tokyo Night v4"
    for src,od,tag in ((OUTV,'',' VERTICAL'),(OUT,'',' 16x9')):
        for a,suf in (('/tmp/sfx4.f32','sfx only - post this'),('/tmp/pv4.f32','preview with song')):
            subprocess.run(['ffmpeg','-v','error','-y','-framerate',str(FPS),'-i',f'{src}/%04d.jpg']+af(a)+['-map','0:v','-map','1:a']+enc+['-c:a','aac','-b:a','256k','-shortest',f'{BASE}/{nm}{tag} ({suf}).mp4'],check=True,stdin=subprocess.DEVNULL)
    print('encoded')
if __name__=='__main__':
    c=sys.argv[1]
    if c=='info': print(F(0),END,TOTAL,len(SEGS)); print([(s['id'],s['c'],s['f0'],s['f1']) for s in SEGS])
    elif c=='extract':
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(4) as ex: list(ex.map(extract,SEGS))
        print('extracted')
    elif c=='masks':
        from rembg import new_session, remove
        sess=new_session('u2net_human_seg'); os.makedirs(MASKD,exist_ok=True)
        for s in SEGS:
            if not s.get('hero'): continue
            for i in range(s['f1']-s['f0']):
                im=sframe(s,i).resize((960,540)); m=remove(im,session=sess,only_mask=True)
                m=m.filter(ImageFilter.GaussianBlur(1.5)).resize((W,H),Image.BILINEAR); m.save(f"{MASKD}/{s['id']}_{i:04d}.png")
        print('masks ok')
    elif c=='render':
        a,b=int(sys.argv[2]),int(sys.argv[3]); os.makedirs(OUT,exist_ok=True); os.makedirs(OUTV,exist_ok=True)
        for f in range(a,b):
            im=render169(f); im.save(f"{OUT}/{f:04d}.jpg",quality=94); wrapv(im,f).save(f"{OUTV}/{f:04d}.jpg",quality=94)
        print('rendered',a,b)
    elif c=='test':
        fs=[int(x) for x in sys.argv[2:]]; ims=[render169(f).resize((384,216)) for f in fs]
        cols=6; rows=(len(ims)+cols-1)//cols; s=Image.new('RGB',(384*cols,216*rows))
        for j,im in enumerate(ims): s.paste(im,((j%cols)*384,(j//cols)*216))
        s.save(f"{BASE}/_work/v4test.jpg",quality=85); print('test ok')
    elif c=='audio': audio()
    elif c=='encode': encode()
