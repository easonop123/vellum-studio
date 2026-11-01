# Vellum Demo 02 — Italy × Plot Twist
import os, sys, math, random, subprocess, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops, ImageFont
sys.path.insert(0,os.path.expanduser('~/vellum'))
import v4 as V
V.BAR=1.9512; V.BEAT=V.BAR/4; V.DROP=3.9024
F=V.F; W,H=V.W,V.H; FPS=V.FPS; HOME=V.HOME
V.BASE=f"{HOME}/mnt/Downloads/Vellum Demo 02 - Italy"; CD=f"{V.BASE}/clips"
for i,f in enumerate(sorted(x for x in os.listdir(CD) if x.endswith('.mp4')),1): V.CL[f'I{i:02d}']=f"{CD}/{f}"
V.FR=f"{HOME}/vellum/fr7"; V.OUT=f"{HOME}/vellum/out7"; V.OUTV=f"{HOME}/vellum/out7v"; V.MASKD=f"{HOME}/vellum/mask7"
V.GRADE=("eq=contrast=1.08:saturation=1.16:gamma=0.98,"
         "colorbalance=rs=-0.02:gs=0:bs=0.05:rm=0.05:gm=0.01:bm=-0.04:rh=0.07:gh=0.03:bh=-0.06,"
         "curves=all='0/0.04 0.25/0.23 0.75/0.80 1/0.97'")
SONG_OFF=31.5604; SONG=f"{V.A}/song_pt_v12_m4.wav"
V.SEGS.clear(); seg=V.seg; SEGS=V.SEGS; SUBS=[]
def sub(c,ss,sp,k0,k1,box=(W,H),fx=.5,fy=.45,raw=False):
    d=dict(c=c,ss=ss,sp=sp,k0=k0,k1=k1,f0=F(k0),f1=F(k1),box=box,fx=fx,fy=fy,raw=raw,id=f"u{len(SUBS):02d}"); SUBS.append(d); return d
# ---------------- HOOK
for i,(c,ss,fy) in enumerate([('I07',6,.45),('I22',2,.6),('I21',4,.45),('I28',3,.45)]): seg(-8+i,-7+i,c,ss,1.0,raw=True,fy=fy,label=f"IMG_{2214+i*9}.MOV")
SEGS[0]['f0']=0
seg(-4,-1,'I07',1,1.0,kind='typed',skip=True)
seg(-1,0,'I12',1,1.0,kind='strobe',skip=True,srcs=[sub('I12',3,1,-1,0,raw=True),sub('I13',9,1,-1,0,raw=True),sub('I16',3,1,-1,0,fy=.3,raw=True)])
# ---------------- BODY
seg(0,3,'I27',0.3,0.45,creep=.05,hero=True,fy=.45)
seg(3,4,'I14',1,1.0,punch=1,title=('Cinque Terre','liguria'))
seg(4,4.5,'I02',3,1.0,tin='whip')
seg(4.5,5,'I08',3,1.0,punch=1,border=1)
seg(5,6.5,'I13',1,1.0,kind='cols',skip=True,cols=[(sub('I13',1.5,1,5,6.5,(640,1080),fx=.3),0),(sub('I13',5,1,5.5,6.5,(640,1080),fx=.45),F(5.5)-F(5)),(sub('I13',8.2,1,6,6.5,(640,1080),fx=.6),F(6)-F(5))])
seg(6.5,7.5,'I13',9.5,0.55,creep=.04)
seg(7.5,8,'I26',4,1.0,fy=.55,tin='whip')
for i,(c,ss,fy) in enumerate([('I01',2.4,.5),('I30',1,.5),('I12',3.4,.5),('I03',6.6,.5)]): seg(8+i*0.5,8.5+i*0.5,c,ss,1.0,punch=1,fy=fy,bw=(2 if i==1 else 0))
seg(10,11,'I33',11.5,0.7,creep=.05)
seg(11,12,'I38',13,1.0,creep=.03)
seg(12,13,'I34',4,1.0,shrink_from=True)
seg(13,13.5,'I25',1,1.0,fy=.6,punch=1)
seg(13.5,14,'I15',7,1.0,fy=.55,strobe_with=True)
seg(14,15,'I29',5,1.0,fy=.35,title=('Roma','lazio'))
seg(15,16,'I16',2.5,(0.7,3.2),fy=.32,zt=5)
seg(16,20,'I20',1,0.45,fy=.55,creep=.08,boom=1,leak=(F(18)-F(16),9),title=('Venezia','veneto',F(17)-F(16)),
    pip=[(sub('I19',4,0.7,18.5,20,fy=.5),F(18.5)-F(16),'tl'),(sub('I06',2,0.7,19,20,fy=.55),F(19)-F(16),'br')])
seg(20,20.5,'I39',3,1.0,fy=.55,tin='whip')
seg(20.5,21,'I17',2,1.0,fy=.5,punch=1)
seg(21,21.5,'I32',2,1.0,fy=.5,punch=1,border=1)
seg(21.5,22,'I10',3,1.0,fy=.5,punch=1)
seg(22,23,'I09',12,1.0,bw=3,title=('Firenze','toscana'))
seg(23,24,'I11',3,1.0,fy=.5,sil=5)
for i,(c,ss,fy) in enumerate([('I35',9,.6),('I36',3,.6),('I31',4,.5),('I18',6,.5)]):
    seg(24+i*0.25,24.25+i*0.25,c,ss,1.0,punch=1,fy=fy,rgb=(i%2==0))
seg(25,26,'I24',2,1.0,creep=.03)
seg(26,29,'I05',3,0.7,fy=.55,creep=.06,shrink_from=True,title=('Positano','campania',F(26.5)-F(26)))
seg(29,32,'I04',4,0.8,creep=.07,ending=1)
V.END=END=F(32); V.TOTAL=TOTAL=F(36)
BLOOMS=[F(0),F(10),F(16),F(32)]
# ---------------- extract / masks
def crop(s):
    w,h,_=V.probe(V.CL[s['c']]); tw,th=s.get('box',(W,H)); a=tw/th
    if w/h>a: cw=int(h*a)//2*2; x=int((w-cw)*s.get('fx',.5))//2*2; return f"crop={cw}:{h}:{x}:0,scale={tw}:{th}:flags=lanczos"
    ch=int(w/a)//2*2; y=int((h-ch)*s.get('fy',.45))//2*2; return f"crop={w}:{ch}:0:{y},scale={tw}:{th}:flags=lanczos"
def extract(s):
    if s.get('skip'): return
    d=f"{V.FR}/{s['id']}"; os.makedirs(d,exist_ok=True); _,n=V.cum(s)
    if len(glob.glob(d+'/*.jpg'))>=n-2: return
    vf=[crop(s)]
    if s.get('interp'): vf.append(f"minterpolate=fps={V.probe(V.CL[s['c']])[2]*2}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
    vf+=[V.RAWL if s.get('raw') else V.GRADE]
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(s['ss']),'-i',V.CL[s['c']],'-vf',','.join(vf),'-frames:v',str(n),'-q:v','2',f"{d}/%04d.jpg"],check=True,stdin=subprocess.DEVNULL)
def mask(s,i):
    p=f"{V.MASKD}/{s['id']}_{i:04d}.png"
    return Image.open(p).convert('L') if os.path.exists(p) else None
def mask_jobs():
    J=[]
    for s in SEGS:
        n=s['f1']-s['f0']
        if s.get('hero'): J+=[(s,i) for i in range(n)]
        if s.get('sil'): J+=[(s,i) for i in range(n-s['sil'],n)]
    return J
# ---------------- helpers
def flashb(im,a): return Image.blend(im,Image.new('RGB',im.size,(255,255,255)),a)
def rgbsplit(im,s):
    a=np.asarray(im).copy(); a[:,:,0]=np.roll(a[:,:,0],s,1); a[:,:,2]=np.roll(a[:,:,2],-s,1); return Image.fromarray(a)
def bloom(im,g):
    a=np.asarray(im,np.float32)*g; sm=Image.fromarray(np.clip(a,0,255).astype(np.uint8)).resize((480,270)).filter(ImageFilter.GaussianBlur(10)).resize((W,H),Image.BILINEAR)
    b=np.asarray(sm,np.float32); a=255-(255-np.clip(a,0,255))*(255-b*min(1,(g-1)))/255; return Image.fromarray(np.clip(a,0,255).astype(np.uint8))
SER=f"{HOME}/fonts/InstrumentSerif-Italic.ttf"
def serif_title(im,t,sub_,i):
    f=ImageFont.truetype(SER,330); fs=V.font(V.JB,34,'Medium')
    n=min(len(t),i+1) if i>=0 else 0; tw=f.getlength(t); x=(W-tw)/2; bb=f.getbbox(t); y=H*0.33-bb[1]
    sh=Image.new('L',(W,H),0); ImageDraw.Draw(sh).text((x+6,y+8),t[:n],font=f,fill=200); sh=sh.filter(ImageFilter.GaussianBlur(14))
    im.paste((0,0,0),(0,0),sh); d=ImageDraw.Draw(im)
    d.text((x,y),t[:n],font=f,fill=(250,246,238))
    if i>=len(t):
        s2=' '.join(sub_.upper()); w2=fs.getlength(s2); d.text(((W-w2)/2,y+bb[3]+10),s2,font=fs,fill=(240,236,228))
    return im
HB=None
def hero7(im,s,i):
    global HB
    ft=V.fit_font(V.ANTON,"ITALIA",W*0.92,start=700)
    bb=ft.getbbox("ITALIA")
    if bb[3]-bb[1]>H*0.5: ft=V.font(V.ANTON,int(ft.size*H*0.5/(bb[3]-bb[1]))); bb=ft.getbbox("ITALIA")
    tw=ft.getlength("ITALIA"); x0=(W-tw)/2; y0=H*0.42-(bb[3]-bb[1])/2-bb[1]
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    n=min(6,(i-2)//2+1) if i>=2 else 0; d.text((x0,y0),"ITALIA"[:n],font=ft,fill=(214,24,32,255))
    out=Image.alpha_composite(im.convert('RGBA'),lay).convert('RGB'); m=mask(s,i)
    if m is not None: out.paste(im,(0,0),m)
    return out
F_LB=V.font(V.ANTON,40)
def labels(im,f):
    if f<F(0) or f>=F(29): return im
    e=f-F(0); beat=e/(V.BEAT*FPS); ph=beat%8
    if ph>=7.0 and int(e)%2==0: return im
    if ph<0.4 and e%2==1: return im
    d=ImageDraw.Draw(im); c=(226,30,38)
    d.text((70,60),"MOMENTS IN",font=V.font(V.ANTON,30),fill=c); d.text((70,92),"ITALIA 2026",font=F_LB,fill=c)
    t1="EDITED BY"; t2="VELLUM STUDIO"; f1=V.font(V.ANTON,30)
    d.text((W-70-f1.getlength(t1),60),t1,font=f1,fill=c); d.text((W-70-F_LB.getlength(t2),92),t2,font=F_LB,fill=c)
    return im
def border(im,j):
    t=[46,30,16][j] if j<3 else 0
    if t: d=ImageDraw.Draw(im); c=(226,30,38); d.rectangle([0,0,W,t],fill=c); d.rectangle([0,H-t,W,H],fill=c); d.rectangle([0,0,t,H],fill=c); d.rectangle([W-t,0,W,H],fill=c)
    return im
def typed(f):
    i=f-F(-4); im=Image.new('RGB',(W,H),(6,6,6)); d=ImageDraw.Draw(im)
    ft=V.font(V.ANTON,330); c=(226,30,38); step=V.BEAT*FPS/2
    k=i/step
    if k<4: t="NEXT"[:int(k)+1]
    else: t="STOP"[:min(4,int((k-4)*2)+1)]
    cur=(i//6)%2==0
    tw=ft.getlength(t); bb=ft.getbbox("NEXT"); x=(W-tw)/2; y=H/2-(bb[3]+bb[1])/2
    d.text((x,y),t,font=ft,fill=c)
    if cur: d.rectangle([x+tw+20,y+bb[3]-28,x+tw+150,y+bb[3]],fill=c)
    return im
def strobe(s,i):
    srcs=s['srcs']; u=srcs[(i//2)%3]; im=V.sframe(u,i)
    if i>=s['f1']-s['f0']-3: im=bloom(im,1.6+0.6*(i-(s['f1']-s['f0']-3)))
    return im
def cols(s,i):
    can=Image.new('RGB',(W,H),(8,8,8))
    for j,(u,a) in enumerate(s['cols']):
        if i>=a:
            p=V.sframe(u,i-a); off=int(90*(1-V.ease((i-a+1)/3))*(1 if j%2==0 else -1))
            can.paste(p,(j*640,off))
            if i==a: can=flashb(can,0.3)
    d=ImageDraw.Draw(can)
    for x in (640,1280): d.rectangle([x-4,0,x+4,H],fill=(8,8,8))
    return can
def shrink_over(im,prev,i,n=8):
    if i>=n: return im
    t=V.ease((i+1)/n); pim=V.base(prev,prev['f1']-prev['f0']+i)
    sc=1-0.62*t; w,h=int(W*sc),int(H*sc); b=10
    fr=Image.new('RGB',(w+2*b,h+2*b),(250,248,244)); fr.paste(pim.resize((w,h)),(b,b))
    x=int((W-fr.size[0])/2+t*t*W*0.9); y=int((H-fr.size[1])/2)
    sh=Image.new('L',fr.size,140); im=im.copy(); im.paste((0,0,0),(x+12,y+16),sh); im.paste(fr,(x,y)); return im
def silflash(im,s,i,n):
    j=i-(n-s['sil']); m=mask(s,i)
    if m is None: return im
    m=m.point(lambda v:255 if v>100 else 0)
    dark=Image.blend(im,Image.new('RGB',(W,H)),0.25+0.12*j)
    glow=m.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(22))
    dark.paste((255,250,240),(0,0),glow.point(lambda v:int(v*0.8))); dark.paste((255,255,255),(0,0),m)
    return dark
def pips(im,s,i):
    for (u,a,pos) in s.get('pip',[]):
        if i>=a:
            pp=V.ease((i-a+1)/4); sc=0.30*(0.7+0.3*pp); w,h=int(W*sc),int(H*sc)
            ins=V.sframe(u,i-a).resize((w,h)); fr=Image.new('RGB',(w+16,h+16),(250,250,246)); fr.paste(ins,(8,8))
            im.paste(fr,(70,170) if pos=='tl' else (W-70-fr.size[0],H-70-fr.size[1]))
            if i==a: im=flashb(im,0.35)
    return im
# ---------------- render
def render(f):
    if f>=END: return V.endcard169(f)
    s=V.seg_at(f); i=f-s['f0']; n=s['f1']-s['f0']; k=SEGS.index(s)
    prev=SEGS[k-1] if k>0 else None; nxt=SEGS[k+1] if k+1<len(SEGS) else None; kd=s.get('kind')
    if kd=='typed': return typed(f)
    if kd=='strobe': return strobe(s,i)
    if kd=='cols': im=cols(s,i)
    else:
        im=V.base(s,i)
        if s.get('raw'):
            d=ImageDraw.Draw(im); d.text((40,H-70),s['label'],font=V.F_L,fill=(255,255,255)); d.text((W-260,40),f"0:0{(i%24)//10}{i%10}",font=V.F_L,fill=(255,255,255)); return im
        if s.get('hero'): im=hero7(im,s,i)
        if s.get('bw') and i<s['bw']: im=V.bw(im)
        if s.get('rgb') and i<3: im=rgbsplit(im,14)
        if s.get('strobe_with') and prev and i>=2 and (i//2)%2==1: im=V.base(prev,prev['f1']-prev['f0']+i)
        if s.get('sil') and i>=n-s['sil']: im=silflash(im,s,i,n)
    t=s.get('tin')
    if t=='whip' and i<3: im=V.mblur(im,[700,380,140][i])
    if nxt and nxt.get('tin')=='whip' and i>=n-3: im=V.mblur(im,[140,380,700][i-(n-3)])
    if s.get('zt') and i>=n-s['zt']: p=(i-(n-s['zt'])+1)/s['zt']; im=V.zoomblur(V.scale_c(im,1+0.9*p*p),0.7*p)
    if s.get('shrink_from') and prev: im=shrink_over(im,prev,i)
    if s.get('leak'):
        a,ln=s['leak']
        if a<=i<a+ln: im=V.burn(im,(i-a)/ln)
    if s.get('boom') or s.get('hero'):
        if i in (1,2): im=V.zoomblur(im,1.0 if i==1 else 0.5)
        if 1<=i<=10: im=V.shake(im,28*0.72**(i-1),6*(1-(i-1)/10),f)
    im=pips(im,s,i)
    if s.get('title'):
        tt=s['title']; t0=tt[2] if len(tt)>2 else 1
        if i>=t0: im=serif_title(im,tt[0],tt[1],i-t0)
    if s.get('ending'):
        ft=ImageFont.truetype(SER,300); d=ImageDraw.Draw(im); txt="Italia"; m=min(6,max(0,i-3)//2+1) if i>=3 else 0
        tw=ft.getlength(txt); bb=ft.getbbox(txt); d.text(((W-tw)/2,H*0.40-bb[1]),txt[:m],font=ft,fill=(245,240,232))
        if i>=18: fs=V.font(V.JB,32,'Medium'); s2="S U M M E R   2 0 2 6"; d.text(((W-fs.getlength(s2))/2,H*0.40+bb[3]-bb[1]+30),s2,font=fs,fill=(245,240,232))
    im=V.finish(im,f)
    if s.get('border') and i<3: im=border(im,i)
    im=labels(im,f)
    if s.get('ending'):
        b0=F(30.5)-s['f0']; bh=int(130+(H/2-130)*V.ease((i-b0)/(n-b0))**2.2) if i>=b0 else int(130*min(1,(i+1)/5))
        d=ImageDraw.Draw(im); d.rectangle([0,0,W,bh],fill=(0,0,0)); d.rectangle([0,H-bh,W,H],fill=(0,0,0))
    for b in BLOOMS:
        if b-2<=f<b: im=bloom(im,[1.5,2.3][f-(b-2)])
        if b<=f<b+3: im=bloom(im,[2.6,1.9,1.35][f-b])
    return im
# ---------------- vertical wrap (TikTok Sans)
TT=f"{HOME}/fonts/TikTokSans.ttf"
def tt(sz,w='Bold'):
    f=ImageFont.truetype(TT,sz); f.set_variation_by_name(w); return f
VW,VH,VY,VHt=1080,1920,656,608
T1=tt(62); T2=tt(34,'Medium'); T3=tt(30,'SemiBold')
def ct(d,y,t,fnt,fill=(255,255,255)): d.text(((VW-d.textlength(t,font=fnt))/2,y),t,font=fnt,fill=fill)
def wrapv(im,f):
    if f>=END: return V.endcardv(f)
    v=Image.new('RGB',(VW,VH),(0,0,0)); v.paste(im.resize((VW,VHt),Image.LANCZOS),(0,VY)); d=ImageDraw.Draw(v)
    if f<F(0): ct(d,500,"the clips they sent me",T1); ct(d,VY+VHt+40,"no edit, no grade",T2,(170,170,170))
    elif f<F(29): ct(d,500,"what i made with them",T1)
    else: ct(d,500,"want yours like this?",T1)
    if f>=F(0):
        d.text((44,VY+VHt+34),"@vellumstudio.edits",font=T3,fill=(200,200,200))
        e=f-F(0)
        if (e//12)%2==0: d.ellipse([VW-300,VY+VHt+44,VW-280,VY+VHt+64],fill=V.BRED)
        d.text((VW-268,VY+VHt+34),f"REC {e//FPS//60:02d}:{e//FPS%60:02d}",font=T3,fill=(230,230,230))
    if f>=F(24): ct(d,1450,"dm me your clips",tt(56))
    return v
# ---------------- audio
def audio():
    SR=48000
    def load(p,off=0.0):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(off),'-i',p,'-f','f32le','-ac','2','-ar',str(SR),'-'],stdin=subprocess.DEVNULL); return np.frombuffer(raw,np.float32).reshape(-1,2).copy()
    S={n:load(f"{V.A}/{n}.wav") for n in ['sfx16_click','sfx15_click_loud','sfx11_riser','sfx11_impact','sfx15_flash','sfx17_dslr','sfx11_whoosh','sfx17_phone','sfx13_shutterT','sfx17_ring','sfx15_shutter_loud']}
    N=int(TOTAL/FPS*SR); mix=np.zeros((N+SR,2),np.float32); rnd=random.Random(21); duck=[]
    def add(n,fr,db,fade=0.0):
        x=S[n]*(10**((db+rnd.uniform(-1.2,1.2))/20)); p=rnd.uniform(-.15,.15); x=x*np.array([1-p,1+p],np.float32)
        if fade: q=int(fade*SR); x[:q]*=np.linspace(0,1,q)[:,None]
        i=max(0,int(round(fr/FPS*SR))); j=min(len(mix),i+len(x)); mix[i:j]+=x[:j-i]
        if n=='sfx11_impact': duck.append((fr/FPS,-3.5))
        if n=='sfx15_flash': duck.append((fr/FPS,-1.5))
    SH=['sfx13_shutterT','sfx17_dslr','sfx15_shutter_loud','sfx17_phone']; c=[0]
    def shut(fr,db=-8): nm=SH[c[0]%4]; add(nm,fr,db+(-3 if nm=='sfx15_shutter_loud' else 0)); c[0]+=1
    for s in SEGS:
        f0=s['f0']; t=s.get('tin'); kd=s.get('kind'); n=s['f1']-f0
        if s.get('raw') and not kd: add('sfx16_click',f0,-9); continue
        if kd=='typed':
            step=V.BEAT*FPS/2
            for j in range(4): add('sfx15_click_loud',int(f0+j*step),-8)
            for j in range(4): add('sfx16_click',int(f0+4*step+j*step/2),-9)
            continue
        if kd=='strobe':
            for j in range(0,n,2): shut(f0+j,-9)
            add('sfx11_riser',F(0)-40,-9,fade=0.5); continue
        if kd=='cols':
            for (u,a) in s['cols']: shut(f0+a,-6); add('sfx16_click',f0+a,-9)
            continue
        if s.get('hero') or s.get('boom'):
            if s.get('boom'): add('sfx11_riser',f0-48,-10,fade=0.8)
            add('sfx11_whoosh',f0-4,-6); add('sfx11_impact',f0,0); add('sfx15_flash',f0,-4); add('sfx15_click_loud',f0,-6)
            if s.get('hero'):
                for j in range(6): add('sfx16_click',f0+2+j*2,-7)
            for (u,a,pos) in s.get('pip',[]): shut(f0+a,-7); add('sfx15_flash',f0+a,-10)
        else:
            shut(f0,-7 if s['k1']-s['k0']<=0.5 else -9)
        if t=='whip': add('sfx11_whoosh',f0-3,-8)
        if s.get('punch'): add('sfx16_click',f0,-10)
        if s.get('border'): add('sfx15_click_loud',f0,-7)
        if s.get('shrink_from'): add('sfx11_whoosh',f0,-9)
        if s.get('strobe_with'):
            for j in range(2,n,4): add('sfx16_click',f0+j,-10)
        if s.get('zt'): add('sfx11_whoosh',s['f1']-5,-6)
        if s.get('sil'): add('sfx15_flash',s['f1']-s['sil'],-6); add('sfx17_ring',s['f1']-s['sil'],-13)
        if s.get('title'):
            tt=s['title']; t0=tt[2] if len(tt)>2 else 1
            for j in range(len(tt[0])): add('sfx16_click',f0+t0+j,-12)
            add('sfx17_ring',f0+t0+len(tt[0]),-14)
        if s.get('ending'):
            for j in range(6): add('sfx16_click',f0+3+j*2,-9)
    for b in BLOOMS: add('sfx15_flash',b,-6)
    add('sfx11_impact',END,-8); add('sfx17_ring',END,-12)
    for j in range(6): add('sfx16_click',END+j*2,-11)
    mix=mix[:N]; sfx=mix*(10**(6/20)); sfx=sfx/max(1,np.abs(sfx).max()/0.89); sfx.astype(np.float32).tofile('/tmp/sfx7.f32')
    song=load(SONG,SONG_OFF)[:N]; song=np.pad(song,((0,max(0,N-len(song))),(0,0)))
    env=np.ones(N,np.float32)
    for t0,db in duck:
        g=1-10**(db/20); lo=int(t0*SR); hi=min(N,lo+int(0.3*SR)); tt_=np.arange(hi-lo)/SR; env[lo:hi]-=g*np.clip(tt_/0.006,0,1)*np.clip(1-(tt_-0.035)/0.22,0,1)
    song*=np.clip(env,0.3,1)[:,None]*10**(-2/20); q=int(1.0*SR); song[-q:]*=np.linspace(1,0,q)[:,None]
    pv=song+mix; pv=pv/max(1,np.abs(pv).max()/0.89); pv.astype(np.float32).tofile('/tmp/pv7.f32'); print('audio ok')
def encode():
    enc=['-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-r',str(FPS)]
    af=lambda p:['-f','f32le','-ar','48000','-ac','2','-i',p]; nm="Vellum Demo 02 - Italy v1"
    for src,tag in ((V.OUTV,' VERTICAL'),(V.OUT,' 16x9')):
        for a,suf in (('/tmp/sfx7.f32','sfx only - post this'),('/tmp/pv7.f32','preview with song')):
            subprocess.run(['ffmpeg','-v','error','-y','-framerate',str(FPS),'-i',f'{src}/%04d.jpg']+af(a)+['-map','0:v','-map','1:a']+enc+['-c:a','aac','-b:a','256k','-shortest',f'{V.BASE}/{nm}{tag} ({suf}).mp4'],check=True,stdin=subprocess.DEVNULL)
    print('encoded')
if __name__=='__main__':
    c=sys.argv[1]
    if c=='info': print(END,TOTAL,len(SEGS),len(SUBS)); print([(s['id'],s['c'],s['f0'],s['f1']) for s in SEGS])
    elif c=='extract':
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(4) as ex: list(ex.map(extract,SEGS+SUBS))
        print('extracted')
    elif c=='masks':
        from rembg import new_session, remove
        sess=new_session('u2net_human_seg'); os.makedirs(V.MASKD,exist_ok=True)
        for s,i in mask_jobs():
            p=f"{V.MASKD}/{s['id']}_{i:04d}.png"
            if os.path.exists(p): continue
            m=remove(V.sframe(s,i).resize((960,540)),session=sess,only_mask=True); m.filter(ImageFilter.GaussianBlur(1.5)).resize((W,H),Image.BILINEAR).save(p)
        print('masks ok')
    elif c=='render':
        a,b=int(sys.argv[2]),int(sys.argv[3]); os.makedirs(V.OUT,exist_ok=True); os.makedirs(V.OUTV,exist_ok=True)
        for f in range(a,b):
            im=render(f); im.save(f"{V.OUT}/{f:04d}.jpg",quality=94); wrapv(im,f).save(f"{V.OUTV}/{f:04d}.jpg",quality=94)
        print('rendered',a,b)
    elif c=='test':
        fs=[int(x) for x in sys.argv[2:]]; ims=[render(f).resize((384,216)) for f in fs]
        cols_=6; rows=(len(ims)+cols_-1)//cols_; s=Image.new('RGB',(384*cols_,216*rows))
        for j,im in enumerate(ims): s.paste(im,((j%cols_)*384,(j//cols_)*216))
        os.makedirs(f"{V.BASE}/_work",exist_ok=True); s.save(f"{V.BASE}/_work/test.jpg",quality=85); print('test ok')
    elif c=='audio': audio()
    elif c=='encode': encode()
