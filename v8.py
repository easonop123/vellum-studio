# Vellum Demo 02 — Italy × Plot Twist
import os, sys, math, random, subprocess, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops, ImageFont
sys.path.insert(0,os.path.expanduser('~/vellum'))
import v4 as V
V.BAR=1.93548; V.BEAT=V.BAR/4; V.DROP=3.871
F=V.F; W,H=V.W,V.H; FPS=V.FPS; HOME=V.HOME
V.BASE=f"{HOME}/mnt/Downloads/Vellum Demo 03 - New York"; CD=f"{V.BASE}/clips"
for i,f in enumerate(sorted(x for x in os.listdir(CD) if x.endswith('.mp4')),1): V.CL[f'Y{i:02d}']=f"{CD}/{f}"
V.FR=f"{HOME}/vellum/fr8"; V.OUT=f"{HOME}/vellum/out8"; V.OUTV=f"{HOME}/vellum/out8v"; V.MASKD=f"{HOME}/vellum/mask8"
V.GRADE=("eq=contrast=1.18:saturation=1.02:gamma=0.95,"
         "colorbalance=rs=-0.06:gs=-0.01:bs=0.08:rm=-0.03:gm=0:bm=0.04:rh=0.04:gh=0.02:bh=-0.03,"
         "curves=all='0/0.03 0.25/0.20 0.75/0.80 1/0.98'")
SONG_OFF=15.504; SONG=f"{V.A}/song_v8_m4.wav"
V.SEGS.clear(); seg=V.seg; SEGS=V.SEGS; SUBS=[]
def sub(c,ss,sp,k0,k1,box=(W,H),fx=.5,fy=.45,raw=False):
    d=dict(c=c,ss=ss,sp=sp,k0=k0,k1=k1,f0=F(k0),f1=F(k1),box=box,fx=fx,fy=fy,raw=raw,id=f"u{len(SUBS):02d}"); SUBS.append(d); return d
# ---------------- HOOK
for i,(c,ss,fy) in enumerate([('Y01',3,.45),('Y05',2,.45),('Y12',4,.45),('Y21',8,.5)]): seg(-8+i,-7+i,c,ss,1.0,raw=True,fy=fy,label=f"IMG_{3108+i*11}.MOV")
SEGS[0]['f0']=0
seg(-4,-1,'Y19',2,1.0,kind='tmask',raw=True,word='NYC',creep=.05)
seg(-1,0,'Y09',1,1.0,kind='strobe',skip=True,srcs=[sub('Y09',3,1,-1,0,raw=True),sub('Y11',5,1,-1,0,raw=True),sub('Y24',12,1,-1,0,raw=True)])
# ---------------- BODY
seg(0,3,'Y17',8,0.55,creep=.05,hero=True,fy=.22)
seg(3,4,'Y11',1,1.0,punch=1,cpop=1,title=('Manhattan','new york'))
seg(4,4.5,'Y03',14,1.0,tin='whip')
seg(4.5,5,'Y07',1,1.0,punch=1,border=1)
seg(5,6.5,'Y34',2,1.0,kind='duo',skip=True,duo=[(sub('Y34',2,1,5,6.5,(960,1080),fy=.3),0),(sub('Y35',2,1,5.5,6.5,(960,1080),fy=.3),F(5.5)-F(5))])
seg(6.5,7.5,'Y31',3,0.7,creep=.04,fy=.4)
seg(7.5,8,'Y23',2,1.0,tin='whip')
for i,(c,ss,fy) in enumerate([('Y28',3.4,.5),('Y30',4,.6),('Y22',1,.5),('Y29',4,.3)]): seg(8+i*0.5,8.5+i*0.5,c,ss,1.0,punch=1,fy=fy,bw=(2 if i==3 else 0))
seg(10,11,'Y09',6,0.7,creep=.05,title=('Times Square','midtown'))
seg(11,12,'Y25',8,1.0,fy=.45,creep=.03)
seg(12,14,'Y18',3,0.6,kind='film',fy=.5,cards=[sub('Y06',8,1,12,14,(560,760),fy=.4),sub('Y13',1,1,12,14,(560,760),fy=.5),sub('Y16',6,1,12,14,(560,760)),sub('Y20',3,1,12,14,(560,760),fy=.5)])
seg(14,15,'Y02',3,1.0,fy=.35,title=('Brooklyn','the bridge'))
seg(15,16,'Y27',9,(0.7,3.2),fy=.45,zt=5)
seg(16,20,'Y15',2,0.5,creep=.07,boom=1,leak=(F(18)-F(16),9),
    pip=[(sub('Y08',3,0.7,18.5,20,fy=.3),F(18.5)-F(16),'tl'),(sub('Y33',6,0.7,19,20,fy=.4),F(19)-F(16),'br')])
seg(20,20.5,'Y24',13,1.0,tin='whip')
seg(20.5,21,'Y20',8,1.0,fy=.6,punch=1)
seg(21,21.5,'Y32',5,1.0,fy=.45,punch=1,border=1)
seg(21.5,22,'Y04',3,1.0,fy=.3,punch=1)
seg(22,23,'Y10',2,1.0,cpop=1,bw=0)
seg(23,24,'Y33',1,1.0,fy=.4,sil=5)
for i,(c,ss,fy) in enumerate([('Y16',12,.5),('Y13',3,.5),('Y21',2,.6),('Y05',5,.5)]):
    seg(24+i*0.25,24.25+i*0.25,c,ss,1.0,punch=1,fy=fy,rgb=(i%2==0))
seg(25,26,'Y01',12,1.0,creep=.03)
seg(26,29,'Y14',1,0.7,fy=.5,creep=.06,shrink_from=True,title=('After Dark','the city that never sleeps',F(26.5)-F(26)))
seg(29,32,'Y06',1,0.7,fy=.45,creep=.07,ending=1,tmask_end=1)
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
    f=V.font(V.ANTON,210); fs=V.font(V.JB,32,'Medium'); T=t.upper()
    n=min(len(T),i+1) if i>=0 else 0; tw=f.getlength(T); x=(W-tw)/2; bb=f.getbbox(T); y=H*0.36-bb[1]
    sh=Image.new('L',(W,H),0); ImageDraw.Draw(sh).text((x+6,y+8),T[:n],font=f,fill=190); sh=sh.filter(ImageFilter.GaussianBlur(12))
    im.paste((0,0,0),(0,0),sh); d=ImageDraw.Draw(im); d.text((x,y),T[:n],font=f,fill=(255,255,255))
    if i>=2:
        p=min(1,(i-2)/5); bw=int(tw*p); d.rectangle([x,y+bb[3]+14,x+bw,y+bb[3]+26],fill=(226,30,38))
    if i>=len(T)+1:
        s2=' '.join(sub_.upper()); d.text((x,y+bb[3]+40),s2,font=fs,fill=(255,255,255))
    return im
HB=None
def hero7(im,s,i):
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    fL=V.fit_font(V.ANTON,"NEW",560,start=600); fR=V.fit_font(V.ANTON,"YORK",540,start=600)
    sz=min(fL.size,fR.size); fL=fR=V.font(V.ANTON,sz); bb=fL.getbbox("YORK"); y0=H*0.45-(bb[1]+bb[3])/2
    n=min(7,(i-2)//2+1) if i>=2 else 0; txt="NEWYORK"[:n]
    d.text((590-fL.getlength("NEW"),y0),txt[:3],font=fL,fill=(214,24,32,255))
    out=Image.alpha_composite(im.convert('RGBA'),lay).convert('RGB'); m=mask(s,i)
    if m is not None: out.paste(im,(0,0),m)
    if n>3: ImageDraw.Draw(out).text((1340,y0),txt[3:],font=fR,fill=(214,24,32))
    return out
F_LB=V.font(V.ANTON,40)
def labels(im,f):
    if f<F(0) or f>=F(29): return im
    e=f-F(0); beat=e/(V.BEAT*FPS); ph=beat%8
    if ph>=7.0 and int(e)%2==0: return im
    if ph<0.4 and e%2==1: return im
    d=ImageDraw.Draw(im); c=(226,30,38)
    d.text((70,60),"MOMENTS IN",font=V.font(V.ANTON,30),fill=c); d.text((70,92),"NEW YORK 2026",font=F_LB,fill=c)
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

def cpop(im):
    hsv=np.asarray(im.convert('HSV')).astype(int); h=hsv[...,0]; sat=hsv[...,1]
    m=((h>22)&(h<46)&(sat>110)).astype(np.float32)
    mi=Image.fromarray((m*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    g=ImageOps.grayscale(im).convert('RGB'); g=ImageOps.autocontrast(g,cutoff=1); g.paste(im,(0,0),mi); return g
def tmask(s,i,n,frame):
    word=s.get('word','NYC'); f=V.font(V.ANTON,760); T=word[:min(len(word),i//4+1)]
    m=Image.new('L',(W,H),0); d=ImageDraw.Draw(m); tw=f.getlength(word); bb=f.getbbox(word)
    d.text(((W-tw)/2,H/2-(bb[1]+bb[3])/2),T,font=f,fill=255)
    out=Image.new('RGB',(W,H),(6,6,6)); out.paste(frame,(0,0),m); return out
def duo(s,i):
    can=Image.new('RGB',(W,H),(8,8,8))
    for j,(u,a) in enumerate(s['duo']):
        if i>=a:
            t=V.ease((i-a+1)/5); p=V.sframe(u,i-a); y=int((1-t)*H*(-1 if j==0 else 1))
            can.paste(p,(j*960,y))
            if i==a: can=flashb(can,0.3)
    ImageDraw.Draw(can).rectangle([956,0,964,H],fill=(8,8,8)); return can
def film(s,i,n):
    bg=V.sframe(s,i).resize((480,270)).filter(ImageFilter.GaussianBlur(8)).resize((W,H),Image.BILINEAR)
    can=Image.blend(bg,Image.new('RGB',(W,H)),0.45); d=ImageDraw.Draw(can)
    off=(i*26)%640
    for k in range(-1,5):
        x=k*640-off+20; d.rectangle([x,140,x+620,940],fill=(14,14,14))
        for h in range(8): d.rectangle([x+20+h*75,158,x+60+h*75,182],fill=(230,230,226)); d.rectangle([x+20+h*75,898,x+60+h*75,922],fill=(230,230,226))
        c=s['cards'][(k+(i*26)//640)%len(s['cards'])]; can.paste(V.sframe(c,i).resize((560,690)),(int(x+30),205))
    return can
# ---------------- render
def render(f):
    if f>=END: return V.endcard169(f)
    s=V.seg_at(f); i=f-s['f0']; n=s['f1']-s['f0']; k=SEGS.index(s)
    prev=SEGS[k-1] if k>0 else None; nxt=SEGS[k+1] if k+1<len(SEGS) else None; kd=s.get('kind')
    if kd=='typed': return typed(f)
    if kd=='strobe': return strobe(s,i)
    if kd=='cols': im=cols(s,i)
    elif kd=='duo': im=duo(s,i)
    elif kd=='film': im=film(s,i,n)
    elif kd=='tmask':
        fr_=V.base(s,i); im=tmask(s,i,n,fr_); d=ImageDraw.Draw(im); d.text((40,H-70),"RAW FOOTAGE",font=V.F_L,fill=(255,255,255)); return im
    else:
        im=V.base(s,i)
        if s.get('raw'):
            d=ImageDraw.Draw(im); d.text((40,H-70),s['label'],font=V.F_L,fill=(255,255,255)); d.text((W-260,40),f"0:0{(i%24)//10}{i%10}",font=V.F_L,fill=(255,255,255)); return im
        if s.get('hero'): im=hero7(im,s,i)
        if s.get('bw') and i<s['bw']: im=V.bw(im)
        if s.get('cpop') and i>=2: im=cpop(im)
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
        if i<16:
            f_=V.font(V.ANTON,700); sc=1+ (max(0,i-6)/10)**3*14; word="NYC"
            m=Image.new('L',(W,H),0); d=ImageDraw.Draw(m); tw=f_.getlength(word); bb=f_.getbbox(word)
            d.text(((W-tw)/2,H/2-(bb[1]+bb[3])/2),word,font=f_,fill=255)
            if sc>1: w2,h2=int(W*sc),int(H*sc); m=m.resize((w2,h2)).crop(((w2-W)//2,(h2-H)//2,(w2-W)//2+W,(h2-H)//2+H))
            bg=Image.new('RGB',(W,H),(6,6,6)); bg.paste(im,(0,0),m); im=bg
        else:
            ft=V.font(V.ANTON,170); d=ImageDraw.Draw(im); txt="NEW YORK"; m=min(8,(i-16)+1)
            tw=ft.getlength(txt); d.text(((W-tw)/2,H*0.36),txt[:m],font=ft,fill=(255,255,255))
            if i>=26: fs=V.font(V.JB,32,'Medium'); s2="E D I T E D   B Y   V E L L U M"; d.text(((W-fs.getlength(s2))/2,H*0.36+220),s2,font=fs,fill=(255,255,255))
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
        if kd in('duo',):
            for (u,a) in s['duo']: shut(f0+a,-6); add('sfx11_whoosh',f0+a-2,-9)
            continue
        if kd=='film':
            for j in range(0,n,5): add('sfx16_click',f0+j,-10)
            add('sfx11_whoosh',f0,-8); continue
        if kd=='tmask':
            for j in range(3): add('sfx15_click_loud',f0+j*4,-7)
            continue
        if kd=='cols':
            for (u,a) in s['cols']: shut(f0+a,-6); add('sfx16_click',f0+a,-9)
            continue
        if s.get('hero') or s.get('boom'):
            if s.get('boom'): add('sfx11_riser',f0-48,-10,fade=0.8)
            add('sfx11_whoosh',f0-4,-6); add('sfx11_impact',f0,0); add('sfx15_flash',f0,-4); add('sfx15_click_loud',f0,-6)
            if s.get('hero'):
                for j in range(8): add('sfx16_click',f0+2+j*2,-7)
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
            add('sfx11_whoosh',f0+8,-6); add('sfx15_flash',f0+16,-6)
            for j in range(8): add('sfx16_click',f0+16+j,-10)
        if s.get('cpop'): add('sfx15_click_loud',f0+2,-7)
    for b in BLOOMS: add('sfx15_flash',b,-6)
    add('sfx11_impact',END,-8); add('sfx17_ring',END,-12)
    for j in range(6): add('sfx16_click',END+j*2,-11)
    mix=mix[:N]; sfx=mix*(10**(6/20)); sfx=sfx/max(1,np.abs(sfx).max()/0.89); sfx.astype(np.float32).tofile('/tmp/sfx8.f32')
    song=load(SONG,SONG_OFF)[:N]; song=np.pad(song,((0,max(0,N-len(song))),(0,0)))
    env=np.ones(N,np.float32)
    for t0,db in duck:
        g=1-10**(db/20); lo=int(t0*SR); hi=min(N,lo+int(0.3*SR)); tt_=np.arange(hi-lo)/SR; env[lo:hi]-=g*np.clip(tt_/0.006,0,1)*np.clip(1-(tt_-0.035)/0.22,0,1)
    song*=np.clip(env,0.3,1)[:,None]*10**(-2/20); q=int(1.0*SR); song[-q:]*=np.linspace(1,0,q)[:,None]
    pv=song+mix; pv=pv/max(1,np.abs(pv).max()/0.89); pv.astype(np.float32).tofile('/tmp/pv8.f32'); print('audio ok')
def encode():
    enc=['-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-r',str(FPS)]
    af=lambda p:['-f','f32le','-ar','48000','-ac','2','-i',p]; nm="Vellum Demo 03 - New York v1"
    for src,tag in ((V.OUTV,' VERTICAL'),(V.OUT,' 16x9')):
        for a,suf in (('/tmp/sfx8.f32','sfx only - post this'),('/tmp/pv8.f32','preview with song')):
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
