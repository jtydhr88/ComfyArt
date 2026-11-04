# poster6 round 4: top-left cookie removed entirely (mint + grain fill); M&M edge + packet spot fixes kept.
# poster6 round 3 (design HOLD on e33e60a6): top-left cookie DRAWN LOCALLY (procedural oat cookie, step 2) - no gold pixels, not from promo-ex01; no light cookie exists in our other washed images (643/wash, 673/batch, 687/next checked).
# (round1 note, superseded by step 2 below) Cookie source was: the chocolate cookie in the box of docs/design/673/next/promo-ex01.webp
#   (tip 2640315d, ellipse centre (2270,1836) r 55x47) -- no gold pixels. Rotated 35deg, scaled 1.45x, dome-shaded:
#   round outline, no bite notch, chunk layout of our cookie -> visibly differs from gold's cookie.
# Also: M&M cookie right edge sharpened (x2262-2292,y1645-1695), packet bottom-right light spot cleaned.
import numpy as np,cv2;from PIL import Image
P='promo-ex01.webp';a=np.array(Image.open(P).convert('RGB')).astype(np.float32);H,W=a.shape[:2];rng=np.random.default_rng(11)
src=a.copy()
# 1) erase old cookie -> per-row mint from clean band
y0,y1,x0,x1=1444,1614,1868,2072
mint=np.median(a[y0:y1,2125:2200],1);reg=np.zeros((H,W),bool);reg[y0:y1,x0:x1]=1;reg[1575:,:1895]=0
for y in range(y0,y1):
    m=reg[y];a[y,m]=mint[y-y0]+rng.normal(0,1.2,(m.sum(),3))
if False:  # round4: design HOLD on b0b7605e -> cookie REMOVED; area left as mint fill from step 1
    # 2) cookie DRAWN LOCALLY (procedural oat cookie; no gold pixels, no promo-ex01 pixels):
    #    irregular crumbly outline (radial noise), oat base + flake/raisin texture, dome shading, drop shadow down-right
    n=200;yy,xx=np.mgrid[0:n,0:n].astype(np.float32);c0=n/2;th=np.arctan2(yy-c0,xx-c0);rr=np.hypot(xx-c0,yy-c0)
    rad=74+sum(rng.uniform(1.0,3.2)*np.sin(k*th+rng.uniform(0,6.3)) for k in (2,3,5,7,11))
    rad+=cv2.resize(rng.normal(0,1.4,(1,90)).astype(np.float32),(n,n))[0][((th+np.pi)/(2*np.pi)*(n-1)).astype(int)]
    inside=(rr<rad).astype(np.float32)
    crumb=(rng.random((n,n))<0.35)&(rr>rad-3)&(rr<rad);inside[crumb]=0
    inside=cv2.morphologyEx(inside,cv2.MORPH_OPEN,np.ones((2,2)))
    base=np.array([214,176,122],np.float32)
    nz=cv2.GaussianBlur(rng.normal(0,1,(n,n)).astype(np.float32),(0,0),2.5)*14+cv2.GaussianBlur(rng.normal(0,1,(n,n)).astype(np.float32),(0,0),0.8)*9
    tex=base+nz[...,None]*np.array([1,0.9,0.7])
    for _ in range(38):  # pale oat flakes
        x,y=rng.integers(30,170,2);cv2.ellipse(tex,(int(x),int(y)),(int(rng.integers(4,9)),int(rng.integers(2,4))),float(rng.uniform(0,180)),0,360,(236,214,170),-1)
    for _ in range(9):   # dark raisins/chips, irregular
        x,y=rng.integers(40,160,2);pts=np.array([(x+rng.integers(-7,8),y+rng.integers(-6,7)) for _ in range(6)],np.int32);cv2.fillConvexPoly(tex,cv2.convexHull(pts),(92,52,34))
    tex=cv2.GaussianBlur(tex,(0,0),0.7)
    hgt=cv2.GaussianBlur(rng.normal(0,1,(n,n)).astype(np.float32),(0,0),4)*30+cv2.GaussianBlur(rng.normal(0,1,(n,n)).astype(np.float32),(0,0),1.5)*8
    gx=cv2.Sobel(hgt,cv2.CV_32F,1,0);gy=cv2.Sobel(hgt,cv2.CV_32F,0,1);tex*=np.clip(1-0.025*(gx+gy),0.75,1.25)[...,None]
    rimd=np.clip((rr-(rad-16))/16,0,1)[...,None];tex=tex*(1-0.45*rimd)+np.array([168,112,62],np.float32)*0.45*rimd
    d=np.hypot((xx-c0+18)/80,(yy-c0+20)/80);tex*=np.clip(1.18-0.42*d,0.62,1.2)[...,None]
    edge=cv2.GaussianBlur(inside,(0,0),3);tex*=(0.8+0.2*edge)[...,None]
    m=cv2.GaussianBlur(inside,(0,0),0.7)[...,None]
    sh=cv2.GaussianBlur(np.roll(np.roll(inside,9,0),7,1),(0,0),7)[...,None]*0.32
    s=0.98;n2=int(n*s);tex=cv2.resize(tex,(n2,n2));m=cv2.resize(m,(n2,n2))[...,None];sh=cv2.resize(sh,(n2,n2))[...,None]
    tx,ty=1968-n2//2,1536-n2//2;R=a[ty:ty+n2,tx:tx+n2]
    R=R*(1-sh);R=tex*m+R*(1-m);a[ty:ty+n2,tx:tx+n2]=R
    ys,xs=np.nonzero(m[...,0]>0.5);print('cookie box',tx+xs.min(),ty+ys.min(),tx+xs.max(),ty+ys.max())
# 3) M&M right edge unsharp
# soft orange blob on M&M right edge: refill with divider-wall colour (row median of x2270-2280), crisp edge at x2252
for y in range(1645,1703):
    a[y,2252:2268]=np.median(a[y,2270:2281],0)+rng.normal(0,1.0,(16,3))
# 4) packet bottom-right light spot: clone packet face from 30px left
r=a[1980:2070,2370:2480];bg=cv2.medianBlur(np.clip(r,0,255).astype(np.uint8),31).astype(np.float32)
hot=(r.mean(2)-bg.mean(2))>6;hot=cv2.dilate(hot.astype(np.uint8),np.ones((5,5)))
w=cv2.GaussianBlur(hot.astype(np.float32),(0,0),1.5)[...,None];print('spot px',int(hot.sum()))
a[1980:2070,2370:2480]=bg*w+r*(1-w)
Image.fromarray(np.clip(a,0,255).astype(np.uint8)).save(P,quality=90,method=6)
