import subprocess, os
from PIL import Image, ImageDraw, ImageFont
H=os.path.expanduser('~'); D=f"{H}/mnt/Downloads"
TT=f"{H}/fonts/TikTokSans.ttf"
def ft(sz,w='Bold'):
    f=ImageFont.truetype(TT,sz); f.set_variation_by_name(w); return f
jobs=[
 ("Vellum Demo 01 - Tokyo Night","Vellum Demo 01 - Tokyo Night v6 VERTICAL (sfx only - post this).mp4",3.875,"Tokyo",
  [("POV: you send me","your tokyo trip clips"),("24 boring clips","→ this")]),
 ("Vellum Demo 02 - Italy","Vellum Demo 02 - Italy v1 VERTICAL (sfx only - post this).mp4",3.90,"Italy",
  [("POV: you send me","your italy trip clips"),("random italy clips","→ this")]),
 ("Vellum Demo 03 - New York","Vellum Demo 03 - New York v1 VERTICAL (sfx only - post this).mp4",3.87,"New York",
  [("POV: you send me","your nyc trip clips"),("rate this edit","out of 10")]),
]
for folder,src,t,name,hooks in jobs:
    for k,(l1,l2) in enumerate(hooks,2):
        im=Image.new('RGBA',(1080,1920),(0,0,0,0)); d=ImageDraw.Draw(im)
        d.rectangle([0,380,1080,640],fill=(0,0,0,255))
        f1=ft(76); f2=ft(76)
        for y,s,c in ((420,l1,(255,255,255)),(515,l2,(255,255,255) if k==2 else (255,77,61))):
            d.text(((1080-d.textlength(s,font=f1))/2,y),s,font=f1,fill=c)
        p=f"/tmp/hook_{name}_{k}.png"; im.save(p)
        out=f"{D}/{folder}/{folder.replace('Vellum Demo','Demo')} - HOOK {k} (post this).mp4"
        subprocess.run(['ffmpeg','-v','error','-y','-i',f"{D}/{folder}/{src}",'-i',p,'-filter_complex',f"[0:v][1:v]overlay=0:0:enable='lt(t,{t})'",'-c:v','libx264','-crf','17','-preset','medium','-c:a','copy',out],check=True,stdin=subprocess.DEVNULL)
        print(out)
