# promo poster4/poster6 patch repair: Telea low-freq base + high-freq texture cloned from clean nearby material (no soft blur)
from PIL import Image
import numpy as np,cv2
a=np.array(Image.open('promo_ex01_lens.png').convert('RGB'))
g=np.array(Image.open('gold_ex01.png').convert('RGB'))
H,W=a.shape[:2]
def hf(x,s=3): x=x.astype(np.float32);return x-cv2.GaussianBlur(x,(0,0),s)
def tfill(a,box,src,feather=6,r=5,mode='hf'):
    x0,y0,x1,y1=box;sx,sy,sw,sh=src
    m=np.zeros((H,W),np.uint8);m[y0:y1,x0:x1]=255
    base=cv2.inpaint(a,cv2.dilate(m,np.ones((7,7),np.uint8)),r,cv2.INPAINT_TELEA).astype(np.float32)
    # low-freq of base via larger blur to drop Telea streaks
    pb=np.pad(base,((20,20),(20,20),(0,0)),mode='edge');lo=cv2.GaussianBlur(pb[y0:y1+40,x0:x1+40],(0,0),8)[20:-20,20:-20]
    S=hf(a[sy:sy+sh,sx:sx+sw]);ty=int(np.ceil((y1-y0)/sh));tx=int(np.ceil((x1-x0)/sw))
    # mirror tiling avoids hard tile seams
    T=np.concatenate([np.concatenate([S if (i+j)%2==0 else S[:,::-1] for i in range(tx)],1) for j in range(ty)],0)[:y1-y0,:x1-x0]
    if mode=='clone':
        R=a[sy:sy+sh,sx:sx+sw];T=np.concatenate([np.concatenate([R if (i+j)%2==0 else R[:,::-1] for i in range(tx)],1) for j in range(ty)],0)[:y1-y0,:x1-x0].astype(np.float32);lo=0
    elif mode=='ring':
        rg=np.zeros((H,W),bool);rg[max(0,y0-25):y1+25,max(0,x0-25):x1+25]=True;rg[y0-5:y1+5,x0-5:x1+5]=False
        lo=np.median(a[rg],0)[None,None,:].astype(np.float32)
    out=np.clip(lo+T,0,255)
    w=np.zeros((y1-y0,x1-x0),np.float32);w[feather:-feather,feather:-feather]=1;w=cv2.GaussianBlur(w,(0,0),feather/2)[...,None]
    a=a.copy();reg=a[y0:y1,x0:x1].astype(np.float32);a[y0:y1,x0:x1]=(out*w+reg*(1-w)).astype(np.uint8);return a
# ---- poster4: restore ottoman / coffee-table tops tinted by the sofa recolour (sofa-only mask)
ha=cv2.cvtColor(a,cv2.COLOR_RGB2HSV);yy,xx=np.mgrid[0:H,0:W]
leak=(((xx>360)&(xx<545)&(yy>1860)&(yy<1935))|((xx>525)&(xx<815)&(yy>1790)&(yy<1910)))&(ha[...,0]>=90)&(ha[...,0]<=120)
leak=cv2.dilate(leak.astype(np.uint8),np.ones((3,3),np.uint8))>0
a[leak]=g[leak]
# ---- poster4 carpet bands above/below CTA pill: weave texture from clean carpet right of the pill
a=tfill(a,(45,1890,395,1960),(590,2110,200,70),mode='clone')
a=tfill(a,(35,2095,555,2205),(590,2105,200,100),mode='clone')
# ---- poster6: mint background above left cookie, box lid, right edge; grain from clean mint
# mint above the left cookie: replace smear pixels (low local texture) with per-row mint; real cookie (textured) kept
y0,y1,x0,x1=1460,1556,1840,2118;col=np.median(a[y0:y1,2125:2200].astype(np.float32),1)[:,None,:]
R=a[y0:y1,x0:x1].astype(np.float32);gy=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY).astype(np.float32)
sd=np.sqrt(np.maximum(cv2.blur(gy**2,(1,11))-cv2.blur(gy,(1,11))**2,0))[y0:y1,x0:x1]
rows=np.arange(y0,y1)[:,None]
sm=((sd<5)|(rows<1515))&(np.abs(R-col).sum(2)>12)
sm=cv2.morphologyEx(sm.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((5,5),np.uint8)).astype(np.float32)
w=cv2.GaussianBlur(sm,(0,0),1.2)[...,None]
fillv=col+np.random.default_rng(3).normal(0,1.2,R.shape)
a[y0:y1,x0:x1]=np.clip(fillv*w+R*(1-w),0,255).astype(np.uint8)
a=tfill(a,(2245,1490,2440,1600),(2440,1960,100,60),mode='ring')
a=tfill(a,(2290,1810,2370,1910),(2440,1960,100,60))
a=tfill(a,(2480,2085,2550,2145),(2440,1960,100,60))
# ---- poster6 blurred top-right cookie cell + its back wall: copy the neighbour cell along the box grid (+120,+50), feathered
sx0,sy0,sx1,sy1=2135,1540,2290,1700;dx,dy=120,50
src=a[sy0:sy1,sx0:sx1].astype(np.float32);dst=a[sy0+dy:sy1+dy,sx0+dx:sx1+dx].astype(np.float32)
w=np.zeros(src.shape[:2],np.float32);w[8:-8,8:-8]=1;w=cv2.GaussianBlur(w,(0,0),4)[...,None]
a[sy0+dy:sy1+dy,sx0+dx:sx1+dx]=(src*w+dst*(1-w)).astype(np.uint8)
# chocolate cell right wall: copy from oreo cell right wall along the grid
src=a[1900:1975,2258:2312].astype(np.float32);dst=a[1805:1880,2308:2362].astype(np.float32)
w=np.zeros(src.shape[:2],np.float32);w[5:-5,5:-5]=1;w=cv2.GaussianBlur(w,(0,0),3)[...,None]
a[1805:1880,2308:2362]=(src*w+dst*(1-w)).astype(np.uint8)
Image.fromarray(a).save('promo_ex01_fixed.png')
