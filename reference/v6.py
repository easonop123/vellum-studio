import os, sys, math, random, subprocess, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops, ImageFont
sys.path.insert(0,os.path.expanduser('~/vellum'))
import v4 as V
V.DROP=3.8805
F=V.F; W,H=V.W,V.H; FPS=V.FPS; HOME=V.HOME; BEAT=V.BEAT
KD=f"{V.BASE}/v6 clips"
for i,f in enumerate(sorted(x for x in os.listdir(KD) if x.endswith('.mp4')),1): V.CL[f'K{i:02d}']=f"{KD}/{f}"
V.FR=f"{HOME}/vellum/fr6"; V.OUT=f"{HOME}/vellum/out6"; V.OUTV=f"{HOME}/vellum/out6v"; V.MASKD=f"{HOME}/vellum/mask6"
V.SEGS.clear(); seg=V.seg; SEGS=V.SEGS; SUBS=[]
def sub(c,ss,sp,k0,k1,box=(W,H),fx=.5,fy=.45,raw=False):
    d=dict(c=c,ss=ss,sp=sp,k0=k0,k1=k1,f0=F(k0),f1=F(k1),box=box,fx=fx,fy=fy,raw=raw,id=f"u{len(SUBS):02d}"); SUBS.append(d); return d
TB=(640,360)
# ---------------- HOOK (2 bars, raw)
for i,(c,ss) in enumerate([('N01',10),('K12',3),('N13',5),('K05',4)]): seg(-8+i,-7+i,c,ss,1.0,raw=True,label=f"IMG_{4821+i*7}.MOV")
SEGS[0]['f0']=0
rawtiles=[('N21',3),('K18',2),('N06',2),('K04',3),('N28',2.0),('N16',4),('N02',1),('K13',4),('K02',3)]
app=[-4,-3.5,-3,-2.5,-1.25,-2,-1.75,-1.5,-2.25]
seg(-4,0,'N28',2.0,1.0,kind='grid9',skip=True,raw=True,zoom=F(0)-F(-1),
    tiles=[(sub(c,ss,1.0,a,0,TB,raw=True),F(a)-F(-4)) for (c,ss),a in zip(rawtiles,app)])
# ---------------- BODY
seg(0,3,'N28',3.2,0.5,interp=True,creep=.06,hero=True)
seg(3,3.5,'N01',6,0.9,tin='whip')
seg(3.5,4,'K12',6,1.0,punch=1)
seg(4,4.5,'K18',2,1.0,tin='whip')
seg(4.5,5.5,'N02',1.5,1.0,punch=1,recolor=F(5)-F(4.5))
seg(5.5,6,'K16',3,1.0,punch=1)
seg(6,7.5,'K02',2,0.8,creep=.12,tin='slit',spaced='ASAKUSA')
seg(7.5,8,'K11',3,1.0,tin='whip')
seg(8,9,'K08',2,1.0,tin='strips')
seg(9,9.5,'K13',4,1.0,punch=1)
seg(9.5,10,'K20',3,1.0,punch=1)
seg(10,10.5,'K01',1.5,1.0,punch=1,fy=.25)
seg(10.5,11,'K22',2,1.0,punch=1)
seg(11,12.5,'N11',6.6,0.5,tin='burn',creep=.05)
tri=seg(12.5,14.5,'K23',4,1.0,kind='tri',skip=True,panels=[(sub('N27',4,1,12.5,14.5,(640,1080)),0),(sub('N10',3,1,13,14.5,(640,1080)),F(13)-F(12.5)),(sub('K19',4,1,13.5,14.5,(640,1080)),F(13.5)-F(12.5))],stick=F(13.75)-F(12.5),trans=F(14)-F(12.5))
into=seg(14.5,15.5,'K23',4,1.0,fy=.28,creep=.03); tri['into']=into
seg(15.5,16.5,'K21',6,0.8,punch=1,fy=.3)
seg(16.5,17.5,'K06',2,1.0,kind='cutout',fg=sub('K21',11,0.8,16.5,17.5,fy=.3),creep=.04)
g9=[('K05',8),('K11',6),('N22',2),('N33',3),('K15',2),('K04',8),('N06',15),('N37',3),('N05',3)]
ga=[17.5,17.75,18,18.25,19,18.5,18.75,19.25,19.5]
seg(17.5,20,'K15',2,1.0,kind='grid9',skip=True,zoom=F(20)-F(19.75),tiles=[(sub(c,ss,1.0,a,20,TB),F(a)-F(17.5)) for (c,ss),a in zip(g9,ga)])
seg(20,21,'K15',3.0,1.0,creep=.04,fy=.35)
seg(21,21.5,'K07',1,1.0,tin='whip',fy=.4)
rv=seg(21.5,23,'K17',2,1.0,creep=.03,reveal=9)
seg(23,24,'N16',5,1.0)
for i,(c,ss) in enumerate([('N13',8),('N21',40),('N29',2.6),('N35',3),('N08',7.6),('N19',1),('N09',4),('N31',2)]):
    seg(24+i*0.25,24.25+i*0.25,c,ss,1.0,punch=1,rgb=(i%2==0),fy=(.35 if c=='N35' else .45))
seg(26,28,'N20',5,(0.6,3.0),zt=5)
seg(28,32,'O19',5,0.4,creep=.08,boom=1,leak=(F(30)-F(28),9),pip=[(sub('N24',12,0.7,30,32),F(30)-F(28),'tl'),(sub('N26',4,0.7,31,32,fy=.3),F(31)-F(28),'br')])
seg(32,32.5,'N33',8,1.0,tin='whip')
seg(32.5,33,'N15',1,1.0,tin='whip')
seg(33,34,'N32',4,1.0,punch=1)
seg(34,36,'O24',2,0.7,creep=.06,ending=1)
V.END=END=F(36); V.TOTAL=TOTAL=F(40)
WHITES={F(0),F(8),F(28)}
# ---------------- extract
def crop(s):
    w,h,_=V.probe(V.CL[s['c']]); tw,th=s.get('box',(W,H)); a=tw/th
    if w/h>a: cw=int(h*a)//2*2; x=int((w-cw)*s.get('fx',.5))//2*2; return f"crop={cw}:{h}:{x}:0,scale={tw}:{th}:flags=lanczos"
    ch=int(w/a)//2*2; y=int((h-ch)*s.get('fy',.45))//2*2; return f"crop={w}:{ch}:0:{y},scale={tw}:{th}:flags=lanczos"
def extract(s):
    if s.get('skip'): return
    d=f"{V.FR}/{s['id']}"; os.makedirs(d,exist_ok=True); _,n=V.cum(s)
    if len(glob.glob(d+'/*.jpg'))>=n-2: return
    vf=[]
    if s.get('interp'): vf.append(f"minterpolate=fps={V.probe(V.CL[s['c']])[2]*2}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
    vf+=[crop(s), V.RAWL if s.get('raw') else V.GRADE]
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(s['ss']),'-i',V.CL[s['c']],'-vf',','.join(vf),'-frames:v',str(n),'-q:v','2',f"{d}/%04d.jpg"],check=True,stdin=subprocess.DEVNULL)
def mask(s,i):
    p=f"{V.MASKD}/{s['id']}_{i:04d}.png"
    return Image.open(p).convert('L') if os.path.exists(p) else None
def mask_jobs():
    J=[]
    for s in SEGS:
        n=s['f1']-s['f0']
        if s.get('hero'): J+=[(s,i) for i in range(n)]
        if s.get('reveal'): J+=[(s,i) for i in range(n-s['reveal'],n)]
        if s.get('kind')=='cutout': J+=[(s['fg'],i) for i in range(n)]
    J.append((into,0)); return J
# ---------------- helpers
def flashb(im,a): return Image.blend(im,Image.new('RGB',im.size,(255,255,255)),a)
def rgbsplit(im,s):
    a=np.asarray(im).copy(); a[:,:,0]=np.roll(a[:,:,0],s,1); a[:,:,2]=np.roll(a[:,:,2],-s,1); return Image.fromarray(a)
def recolor(im):
    hsv=np.asarray(im.convert('HSV')).copy(); h=hsv[...,0].astype(int); sat=hsv[...,1]; v=hsv[...,2]
    m=(h>22)&(h<52)&(sat>90)&(v>70); hsv[...,0]=np.where(m,250,h).astype(np.uint8); return Image.fromarray(hsv,'HSV').convert('RGB')
HB=None
def hero6(im,s,i):
    global HB
    if HB is None:
        xm=W
        for j in range(0,s['f1']-s['f0'],3):
            m=mask(s,j)
            if m is None: continue
            a=np.asarray(m.resize((480,270)),np.float32)/255; idx=np.where((a>0.5).mean(0)>0.06)[0]
            if len(idx): xm=min(xm,idx[0]*4)
        right=max(W*0.45,xm-40); left=70; ft=V.fit_font(V.ANTON,"TOKYO",right-left,start=760)
        bb=ft.getbbox("TOKYO")
        if bb[3]-bb[1]>H*0.62: ft=V.font(V.ANTON,int(ft.size*H*0.62/(bb[3]-bb[1]))); bb=ft.getbbox("TOKYO")
        HB=(ft,left,H*0.47-(bb[3]-bb[1])/2-bb[1])
    ft,x0,y0=HB; lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    n=min(5,(i-2)//2+1) if i>=2 else 0; d.text((x0,y0),"TOKYO"[:n],font=ft,fill=V.RED+(255,))
    out=Image.alpha_composite(im.convert('RGBA'),lay).convert('RGB'); m=mask(s,i)
    if m is not None: out.paste(im,(0,0),m)
    return out
F_SP=V.font(V.SG,190,'Bold')
def spaced(im,word,i,n):
    lay=Image.new('L',(W,H),0); d=ImageDraw.Draw(lay); k=len(word); span=W*0.74; x0=(W-span)/2
    order=random.Random(11).sample(range(k),k); al=[0]*k
    for r,j in enumerate(order):
        t=(i-3-r*1.5)/3; al[j]=max(0,min(1,t))
    if i>n-5: al=[a*max(0,(n-i)/5) for a in al]
    for j,ch in enumerate(word):
        if al[j]<=0: continue
        cx=x0+span*j/(k-1); w=d.textlength(ch,font=F_SP); y=H*0.44-int(18*(1-al[j]))
        d.text((cx-w/2,y-95),ch,font=F_SP,fill=int(255*al[j]))
    glow=lay.filter(ImageFilter.GaussianBlur(18)); a=np.asarray(im,np.float32)
    g=np.asarray(glow,np.float32)[...,None]/255*0.9; t=np.asarray(lay,np.float32)[...,None]/255
    a=255-(255-a)*(1-g); a=a*(1-t)+255*t; return Image.fromarray(np.clip(a,0,255).astype(np.uint8))
def outline_place(can,img,m,x,y,olw=1.0):
    ol=m.filter(ImageFilter.MaxFilter(17))
    sh=ol.filter(ImageFilter.GaussianBlur(14)).point(lambda v:int(v*0.5)); can.paste((0,0,0),(x+10,y+16),sh)
    if olw>0: can.paste((255,255,255),(x,y),ol.point(lambda v:int(v*olw)))
    can.paste(img,(x,y),m)
_stk={}
def sticker_src(sg):
    if 'k' in _stk: return _stk['k']
    full=V.sframe(sg,0); m=mask(sg,0) or Image.new('L',(W,H),0)
    m=m.point(lambda v:255 if v>110 else 0).filter(ImageFilter.GaussianBlur(1)); bx=m.getbbox() or (0,0,W,H)
    _stk['k']=(full,m,((bx[0]+bx[2])/2,(bx[1]+bx[3])/2)); return _stk['k']
def place(can,full,m,nat,sc,ctr,olw=1.0):
    w,h=int(W*sc),int(H*sc); x=int(ctr[0]-nat[0]*sc); y=int(ctr[1]-nat[1]*sc)
    outline_place(can,full.resize((w,h),Image.BILINEAR),m.resize((w,h)),x,y,olw)
def tri_frame(s,i,n):
    can=Image.new('RGB',(W,H),(8,8,8))
    for j,(u,a) in enumerate(s['panels']):
        if i>=a:
            can.paste(V.sframe(u,i-a),(j*640,int(70*(1-V.ease((i-a+1)/3)))))
            if i==a: can=flashb(can,0.35)
    d=ImageDraw.Draw(can)
    for x in (640,1280): d.rectangle([x-4,0,x+4,H],fill=(8,8,8))
    st,tr=s['stick'],s['trans']
    if i>=st:
        full,m,nat=sticker_src(s['into'])
        if i<tr:
            can=Image.blend(can,Image.new('RGB',(W,H)),0.35); p=min(1,(i-st+1)/3); place(can,full,m,nat,0.62*(1+0.14*(1-p)**2),(W/2,H/2+30))
            if i==st: can=flashb(can,0.3)
        else:
            t=V.ease((i-tr+1)/(n-tr)); sc=0.62+0.38*t; ctr=((1-t)*W/2+t*nat[0],(1-t)*(H/2+30)+t*nat[1])
            can=Image.blend(Image.blend(can,Image.new('RGB',(W,H)),0.35),full,t); place(can,full,m,nat,sc,ctr,1-t)
    return can
def grid9(s,i,n):
    can=Image.new('RGB',(W,H),(8,8,8))
    for j,(u,a) in enumerate(s['tiles']):
        if i>=a:
            p=V.sframe(u,i-a)
            if i-a<3: p=V.scale_c(p,1+0.25*(1-(i-a)/3)**2)
            if i==a: p=flashb(p,0.45)
            can.paste(p,((j%3)*640,(j//3)*360))
    d=ImageDraw.Draw(can)
    for x in (640,1280): d.rectangle([x-3,0,x+3,H],fill=(8,8,8))
    for y in (360,720): d.rectangle([0,y-3,W,y+3],fill=(8,8,8))
    z=s['zoom']
    if i>=n-z:
        t=V.ease((i-(n-z)+1)/z); can=V.scale_c(can,1+2*t)
        if t>0.5: can=V.zoomblur(can,0.5*t)
    return can
def strips_in(cur,prev,i):
    out=prev.copy(); bh=H//3
    for j in range(3):
        t=V.ease((i-j*0.8+1)/4)
        if t<=0: continue
        dx=int((1-t)*W*(1 if j%2==0 else -1)); band=cur.crop((0,j*bh,W,(j+1)*bh)); out.paste(band,(dx,j*bh))
    return out
def slit_in(cur,prev,i):
    t=V.ease((i+1)/5); w=int(W*t); x=(W-w)//2; out=prev.copy()
    if w>0: out.paste(cur.crop((x,0,x+w,H)),(x,0)); d=ImageDraw.Draw(out); d.rectangle([x-3,0,x,H],fill=(255,255,255)); d.rectangle([x+w,0,x+w+3,H],fill=(255,255,255))
    return out
def cutout(s,i,n):
    bg=V.sframe(s,i); bg=V.scale_c(bg,1+0.05*i/n); fg=V.sframe(s['fg'],i); m=mask(s['fg'],i)
    can=Image.blend(bg,Image.new('RGB',(W,H)),0.15)
    if m is None: return can
    m=m.point(lambda v:255 if v>110 else 0).filter(ImageFilter.GaussianBlur(1))
    sc=0.82; w,h=int(W*sc),int(H*sc); t=V.ease((i+1)/6); x=int((W-w)/2+120+(1-t)*W*0.7); y=int(H-h+40)
    outline_place(can,fg.resize((w,h),Image.BILINEAR),m.resize((w,h)),x,y)
    return can
def reveal(im,s,i,n,nxt):
    R=s['reveal']; j=i-(n-R); t=j/(R-1); m=mask(s,i)
    if m is None: return im
    nb=V.sframe(nxt,0); bx=m.getbbox() or (0,0,W,H); cx=(bx[0]+bx[2])/2; cy=(bx[1]+bx[3])/2
    sc=1+5.5*t**2.2; w,h=int(W*sc),int(H*sc); big=Image.new('L',(W,H),0); big.paste(m.resize((w,h)),(int(cx-cx*sc),int(cy-cy*sc)))
    out=im.copy(); out.paste((255,255,255),(0,0),big.filter(ImageFilter.MaxFilter(9)).point(lambda v:int(v*(1-t)))); out.paste(nb,(0,0),big)
    out=Image.blend(out,nb,max(0,(t-0.45)/0.55)**1.5)
    return flashb(out,0.35) if j==0 else out
def pips(im,s,i):
    for (u,a,pos) in s.get('pip',[]):
        if i>=a:
            pp=V.ease((i-a+1)/4); sc=0.30*(0.7+0.3*pp); w,h=int(W*sc),int(H*sc)
            ins=V.sframe(u,i-a).resize((w,h)); fr=Image.new('RGB',(w+16,h+16),(250,250,246)); fr.paste(ins,(8,8))
            im.paste(fr,(70,70) if pos=='tl' else (W-70-fr.size[0],H-70-fr.size[1]))
            if i==a: im=flashb(im,0.35)
    return im
def glitch(im,j):
    r=random.Random(j*7); a=np.asarray(im,np.float32)
    a=a*np.array([1.0,0.25,0.22])+np.array([90,0,0]); a=np.clip(a*1.4,0,255).astype(np.uint8)
    for _ in range(6):
        y=r.randrange(0,H-80); hh=r.randrange(20,90); a[y:y+hh]=np.roll(a[y:y+hh],r.randrange(-160,160),1)
    im=rgbsplit(Image.fromarray(a),14)
    if j==2: d=ImageDraw.Draw(im); x=r.randrange(500,1200); d.rectangle([x,0,x+170,H],fill=(40,220,225))
    return im
# ---------------- render
def render(f):
    if f>=END: return V.endcard169(f)
    s=V.seg_at(f); i=f-s['f0']; n=s['f1']-s['f0']; k=SEGS.index(s)
    prev=SEGS[k-1] if k>0 else None; nxt=SEGS[k+1] if k+1<len(SEGS) else None; kd=s.get('kind')
    if kd=='tri': im=tri_frame(s,i,n)
    elif kd=='grid9': im=grid9(s,i,n)
    elif kd=='cutout': im=cutout(s,i,n)
    else:
        im=V.base(s,i)
        if s.get('raw'):
            d=ImageDraw.Draw(im); d.text((40,H-70),s['label'],font=V.F_L,fill=(255,255,255)); d.text((W-260,40),f"0:0{(i%24)//10}{i%10}",font=V.F_L,fill=(255,255,255)); return im
        if s.get('hero'): im=hero6(im,s,i)
        if s.get('recolor') is not None and i>=s['recolor']: im=recolor(im)
        if s.get('rgb') and i<3: im=rgbsplit(im,14)
        if s.get('spaced'): im=spaced(im,s['spaced'],i,n)
        if s.get('reveal') and i>=n-s['reveal']: im=reveal(im,s,i,n,nxt)
    if s.get('raw'): return im
    t=s.get('tin')
    if t in('strips','slit') and prev and i<6:
        pim=V.base(prev,prev['f1']-prev['f0']+i) if not prev.get('kind') else Image.new('RGB',(W,H))
        im=strips_in(im,pim,i) if t=='strips' else slit_in(im,pim,i)
    if t=='whip' and i<3: im=V.mblur(im,[700,380,140][i])
    if nxt and nxt.get('tin')=='whip' and i>=n-3: im=V.mblur(im,[140,380,700][i-(n-3)])
    if t=='burn' and i<6: im=V.burn(im,0.45+i*0.1)
    if nxt and nxt.get('tin')=='burn' and i>=n-4: im=V.burn(im,(i-(n-4))*0.12+0.05)
    if s.get('zt') and i>=n-s['zt']: p=(i-(n-s['zt'])+1)/s['zt']; im=V.zoomblur(V.scale_c(im,1+0.9*p*p),0.7*p)
    if s.get('leak'):
        a,ln=s['leak']
        if a<=i<a+ln: im=V.burn(im,(i-a)/ln)
    if s.get('boom') or s.get('hero'):
        if i in (1,2): im=V.zoomblur(im,1.0 if i==1 else 0.5)
        if 1<=i<=10: im=V.shake(im,30*0.72**(i-1),6*(1-(i-1)/10),f)
    im=pips(im,s,i)
    if s.get('ending') and i>=2:
        d=ImageDraw.Draw(im); ft=V.font(V.ANTON,150); m=min(5,(i-2)+1); tw=ft.getlength("TOKYO"); d.text(((W-tw)/2,H/2-120),"TOKYO"[:m],font=ft,fill=V.BONE)
    im=V.finish(im,f)
    if s.get('ending'):
        b0=F(35)-s['f0']; bh=int(138+(H/2-138)*V.ease((i-b0)/(n-6-b0))**2.2) if i>=b0 else int(138*min(1,(i+1)/4))
        d=ImageDraw.Draw(im); d.rectangle([0,0,W,bh],fill=(0,0,0)); d.rectangle([0,H-bh,W,H],fill=(0,0,0))
        if i>=n-5: im=glitch(V.base(s,i),i-(n-5))
    if f in WHITES: im=Image.new('RGB',(W,H),(255,255,255))
    if f-1 in WHITES: im=flashb(im,0.45)
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
    elif f<F(34): ct(d,500,"what i made with them",T1)
    else: ct(d,500,"want yours like this?",T1)
    if f>=F(0):
        d.text((44,VY+VHt+34),"@vellumstudio.edits",font=T3,fill=(200,200,200))
        e=f-F(0)
        if (e//12)%2==0: d.ellipse([VW-300,VY+VHt+44,VW-280,VY+VHt+64],fill=V.BRED)
        d.text((VW-268,VY+VHt+34),f"REC {e//FPS//60:02d}:{e//FPS%60:02d}",font=T3,fill=(230,230,230))
    if f>=F(28): ct(d,1450,"dm me your clips",tt(56))
    return v
# ---------------- audio (shutter heavy)
def audio():
    SR=48000
    def load(p):
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',p,'-f','f32le','-ac','2','-ar',str(SR),'-'],stdin=subprocess.DEVNULL); return np.frombuffer(raw,np.float32).reshape(-1,2).copy()
    S={n:load(f"{V.A}/{n}.wav") for n in ['sfx16_click','sfx15_click_loud','sfx11_riser','sfx11_impact','sfx15_flash','sfx17_dslr','sfx11_whoosh','sfx17_phone','sfx13_shutterT','sfx17_ring','sfx15_shutter_loud','sfx_glitch']}
    N=int(TOTAL/FPS*SR); mix=np.zeros((N+SR,2),np.float32); rnd=random.Random(9); duck=[]
    def add(n,fr,db,fade=0.0):
        x=S[n]*(10**((db+rnd.uniform(-1.2,1.2))/20)); p=rnd.uniform(-.15,.15); x=x*np.array([1-p,1+p],np.float32)
        if fade: q=int(fade*SR); x[:q]*=np.linspace(0,1,q)[:,None]
        i=max(0,int(round(fr/FPS*SR))); j=min(len(mix),i+len(x)); mix[i:j]+=x[:j-i]
        if n=='sfx11_impact': duck.append((fr/FPS,-3.5))
        if n=='sfx15_flash': duck.append((fr/FPS,-1.5))
    SH=['sfx13_shutterT','sfx17_dslr','sfx15_shutter_loud','sfx17_phone']; c=[0]
    def shut(fr,db=-8): add(SH[c[0]%4],fr,db+(-3 if SH[c[0]%4]=='sfx15_shutter_loud' else 0)); c[0]+=1
    for s in SEGS:
        f0=s['f0']; t=s.get('tin'); kd=s.get('kind')
        if s.get('raw') and kd!='grid9': add('sfx16_click',f0,-9); continue
        if kd=='grid9':
            for (u,a) in s['tiles']: add('sfx16_click',f0+a,-7); shut(f0+a,-11)
            z0=s['f1']-s['zoom']; add('sfx11_whoosh',z0,-6)
            if s.get('raw'): add('sfx11_riser',F(0)-40,-10,fade=0.6)
            continue
        if s.get('hero') or s.get('boom'):
            if s.get('boom'): add('sfx11_riser',f0-48,-10,fade=0.8); add('sfx11_whoosh',f0-4,-6)
            add('sfx11_impact',f0,0); add('sfx15_flash',f0,-4); add('sfx15_click_loud',f0,-6)
            if s.get('hero'):
                for j in range(5): add('sfx16_click',f0+2+j*2,-7)
                add('sfx17_ring',f0+11,-12)
            for (u,a,pos) in s.get('pip',[]): shut(f0+a,-7); add('sfx15_flash',f0+a,-10)
            continue
        if kd=='tri':
            for (u,a) in s['panels']: shut(f0+a,-6)
            add('sfx15_click_loud',f0+s['stick'],-5); add('sfx17_ring',f0+s['stick'],-12); add('sfx11_whoosh',f0+s['trans']-2,-7); continue
        if kd=='cutout': add('sfx11_whoosh',f0-2,-8); shut(f0+3,-6); continue
        shut(f0,-7 if s['k1']-s['k0']<=0.5 else -9)
        if t in('whip','strips','slit'): add('sfx11_whoosh',f0-3,-8)
        if t=='burn': add('sfx11_whoosh',f0-4,-10); add('sfx15_flash',f0,-9)
        if s.get('punch'): add('sfx16_click',f0,-10)
        if s.get('recolor') is not None: add('sfx15_click_loud',f0+s['recolor'],-6)
        if s.get('spaced'):
            for j in range(len(s['spaced'])): add('sfx16_click',f0+3+int(j*1.5),-12)
            add('sfx17_ring',f0+8,-13)
        if s.get('reveal'): r0=s['f1']-s['reveal']; add('sfx15_flash',r0,-9); add('sfx11_whoosh',r0+2,-8)
        if s.get('zt'): add('sfx11_whoosh',s['f1']-5,-6)
        if s.get('ending'):
            for j in range(5): add('sfx16_click',f0+2+j,-9)
            add('sfx_glitch',s['f1']-5,-8); add('sfx11_impact',s['f1']-5,-6)
    for w in WHITES: add('sfx15_flash',w,-6)
    add('sfx15_flash',END,-5); add('sfx17_ring',END,-12)
    for j in range(6): add('sfx16_click',END+j*2,-11)
    mix=mix[:N]; sfx=mix*(10**(6/20)); sfx=sfx/max(1,np.abs(sfx).max()/0.89); sfx.astype(np.float32).tofile('/tmp/sfx6.f32')
    song=load(f"{V.A}/song_wdim_v17c_m4.wav")[:N]; song=np.pad(song,((0,max(0,N-len(song))),(0,0)))
    env=np.ones(N,np.float32)
    for t0,db in duck:
        g=1-10**(db/20); lo=int(t0*SR); hi=min(N,lo+int(0.3*SR)); tt_=np.arange(hi-lo)/SR; env[lo:hi]-=g*np.clip(tt_/0.006,0,1)*np.clip(1-(tt_-0.035)/0.22,0,1)
    song*=np.clip(env,0.3,1)[:,None]*10**(-2/20); q=int(0.5*SR); song[-q:]*=np.linspace(1,0,q)[:,None]
    pv=song+mix; pv=pv/max(1,np.abs(pv).max()/0.89); pv.astype(np.float32).tofile('/tmp/pv6.f32'); print('audio ok')
def encode():
    enc=['-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-r',str(FPS)]
    af=lambda p:['-f','f32le','-ar','48000','-ac','2','-i',p]; nm="Vellum Demo 01 - Tokyo Night v6"
    for src,tag in ((V.OUTV,' VERTICAL'),(V.OUT,' 16x9')):
        for a,suf in (('/tmp/sfx6.f32','sfx only - post this'),('/tmp/pv6.f32','preview with song')):
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
        cols=6; rows=(len(ims)+cols-1)//cols; s=Image.new('RGB',(384*cols,216*rows))
        for j,im in enumerate(ims): s.paste(im,((j%cols)*384,(j//cols)*216))
        s.save(f"{V.BASE}/_work/v6test.jpg",quality=85); print('test ok')
    elif c=='vtest':
        fs=[int(x) for x in sys.argv[2:]]; ims=[wrapv(render(f),f).resize((270,480)) for f in fs]
        s=Image.new('RGB',(270*len(ims),480))
        for j,im in enumerate(ims): s.paste(im,(j*270,0))
        s.save(f"{V.BASE}/_work/v6vtest.jpg",quality=85); print('vtest ok')
    elif c=='audio': audio()
    elif c=='encode': encode()
