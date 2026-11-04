# #673 promo ex02 (app examples/01): $0 local restore of 双11 platform/festival words per WASH-SOP B.2.
# Numbers/dates/shop copy stay ours (TIME 10.24-11.11, 10/25开启). Input: main's examples/01.webp.
import sys,numpy as np
from PIL import Image,ImageDraw,ImageFont
src,gold,out=sys.argv[1:4]
B='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc';R='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
F=lambda s,f=B:ImageFont.truetype(f,s,index=0)
k=1690/1024
im=Image.open(src).convert('RGB');g=Image.open(gold).convert('RGB');a=np.array(im)
S=lambda *v:tuple(int(round(x*k)) for x in v)
def hfill(x0,y0,x1,y1):
    # fill box by linear interpolation between left/right edge columns (keeps band gradient)
    L=a[y0:y1,x0-3].astype(float);Rr=a[y0:y1,x1+3].astype(float)
    t=np.linspace(0,1,x1-x0)[None,:,None]
    a[y0:y1,x0:x1]=(L[:,None]*(1-t)+Rr[:,None]*t).astype(np.uint8)
def solid(x0,y0,x1,y1,c): a[y0:y1,x0:x1]=c
# B: green band 冬季专场 -> 双11狂欢
bx=S(18,215,200,285);hfill(*bx)
tc=(214,64,104)
# C: pill 限时特惠 -> 双11狂欢 (pill bg sampled)
px=S(131,355,207,371);pc=tuple(int(v) for v in a[px[1]+2,px[0]+4]);solid(*px,pc)
# mid: 冬季热卖 -> 双11热卖 (white label), 年终专享 -> 双11专享
lx=S(316,95+545,406,120+545);solid(*lx,(255,255,255))
vx=S(310,322+545,340,422+545);solid(*vx,(255,255,255))
im=Image.fromarray(a);d=ImageDraw.Draw(im)
d.text(((bx[0]+bx[2])//2,(bx[1]+bx[3])//2),'双11狂欢',font=F(int(40*k)),fill=tc,anchor='mm')
d.text(((px[0]+px[2])//2,(px[1]+px[3])//2),'双11狂欢',font=F(int(14*k)),fill='white',anchor='mm')
d.text(((lx[0]+lx[2])//2,(lx[1]+lx[3])//2),'双11热卖',font=F(int(21*k)),fill=(200,20,30),anchor='mm')
fv=F(int(22*k));cx=(vx[0]+vx[2])//2;y=vx[1]+int(2*k)
for ch in ['双','11','专','享']:
    f=fv if ch!='11' else F(int(17*k));d.text((cx,y),ch,font=f,fill='black',anchor='mt');y+=int(24.5*k)
# A: 双11礼遇季 festival tag copied from gold (tag only, no TIME/brand), placed above card 1 + our TIME line
t=g.crop(S(24,52,132,72));im.paste(t,S(14,22)[0:2])
d.text(S(140,32),'TIME: 10.24 - 11.11',font=F(int(11*k),R),fill=(150,140,150),anchor='lm')
# D: 双11预售 badge from gold onto card right-2 top-right + our TIME line
im.paste(g.crop(S(846,160,950,186)),S(850,156)[0:2])
d.text(S(648,184),'TIME: 10/25开启',font=F(int(13*k)),fill=(40,80,140),anchor='lm')
im.save(out,'WEBP',quality=90)
