# SUPERSEDED step 2 (gold cookie pixels) by p6_fix2.py per tech-lead wash ruling: top-left cookie now comes from our own washed promo-ex01.webp chocolate cookie (2270,1836), not gold.
# poster6 only: restore a complete domed top-left cookie from gold pixels (cookie only, no gold copy), mirror-clone soft cookie edges
import numpy as np,cv2;from PIL import Image
a=np.array(Image.open('promo_ex01_fixed.png').convert('RGB')).astype(np.float32);g=np.array(Image.open('gold_ex01.png').convert('RGB'))
H,W=a.shape[:2];rng=np.random.default_rng(7)
# 1) clear old sliced half + debris to mint (per-row median of clean column band)
y0,y1,x0,x1=1462,1618,1855,2102
reg=np.zeros((H,W),bool);reg[y0:y1,x0:x1]=1;reg[1575:,:1895]=0;reg[1585:,2078:]=0
mint=np.median(a[y0:y1,2125:2200],1)
for y in range(y0,y1):
    m=reg[y];a[y,m]=mint[y-y0]+rng.normal(0,1.2,(m.sum(),3))
# 2) gold cookie mask (brown/cream, not yellow bg, not olive BONBUN letters)
gc=g[1385:1625,1850:2080];hv=cv2.cvtColor(gc,cv2.COLOR_RGB2HSV)
yel=(hv[...,0]>=21)&(hv[...,0]<=36)&(hv[...,1]>110)
m=(~yel).astype(np.uint8)
m=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
n,l,st,_=cv2.connectedComponentsWithStats(m);k=1+np.argmax(st[1:,4]);m=(l==k).astype(np.uint8)
cs,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE);m=np.zeros_like(m);cv2.drawContours(m,cs,-1,1,-1)
# drop yellow-ish spill fringe
m=cv2.erode(m,np.ones((2,2),np.uint8))
ys,xs=np.nonzero(m);by0,by1,bx0,bx1=ys.min(),ys.max()+1,xs.min(),xs.max()+1
ck=gc[by0:by1,bx0:bx1].astype(np.float32);mk=m[by0:by1,bx0:bx1].astype(np.float32)
s=0.74;nw,nh=int(ck.shape[1]*s),int(ck.shape[0]*s)
ck=cv2.resize(ck,(nw,nh),interpolation=cv2.INTER_AREA);mk=cv2.resize(mk,(nw,nh),interpolation=cv2.INTER_AREA)
mk=cv2.GaussianBlur(mk,(0,0),0.6)[...,None]
# despill yellow edge: pull fringe toward mint
cx,by=1968,1617;px,py=cx-nw//2,by-nh
a[py:py+nh,px:px+nw]=ck*mk+a[py:py+nh,px:px+nw]*(1-mk)
print('cookie box',px,py,px+nw,py+nh)
# 2b) soft contact shadow none (gold has none)
def exemplar(poly,P=9,R=70,cb=None):
    """Criminisi-style patch inpaint: fill hand-drawn polygon from best-matching sharp local patches (no blur)."""
    global a
    M=np.zeros((H,W),np.uint8);cv2.fillPoly(M,[np.array(poly,np.int32)],1);M=M.astype(bool)
    ys,xs=np.nonzero(M);Y0,Y1,X0,X1=ys.min()-R,ys.max()+R,xs.min()-R,xs.max()+R
    A=a[Y0:Y1,X0:X1].copy();m=M[Y0:Y1,X0:X1].copy();h=P//2
    from numpy.lib.stride_tricks import sliding_window_view as sw
    valid=~sw(m,(P,P)).any((2,3))
    if cb is not None:
        cm=np.zeros(m.shape,bool);cm[max(cb[1]-Y0,0):cb[3]-Y0,max(cb[0]-X0,0):cb[2]-X0]=1;valid&=sw(cm,(P,P)).all((2,3))
    SW=sw(A,(P,P),axis=(0,1))  # (y,x,3,P,P)
    vy,vx=np.nonzero(valid);cand=SW[vy,vx]  # N,3,P,P
    while m.any():
        k=cv2.filter2D((~m).astype(np.float32),-1,np.ones((P,P)))
        fr=m&(cv2.dilate((~m).astype(np.uint8),np.ones((3,3)))>0)
        fy,fx=np.nonzero(fr);t=np.argmax(k[fy,fx]);cy,cx=fy[t],fx[t]
        cy=np.clip(cy,h,A.shape[0]-h-1);cx=np.clip(cx,h,A.shape[1]-h-1)
        tp=A[cy-h:cy+h+1,cx-h:cx+h+1].transpose(2,0,1);kn=~m[cy-h:cy+h+1,cx-h:cx+h+1]
        d=(((cand-tp)**2)*kn).sum((1,2,3));b=np.argmin(d)
        src=cand[b].transpose(1,2,0);u=m[cy-h:cy+h+1,cx-h:cx+h+1]
        A[cy-h:cy+h+1,cx-h:cx+h+1][u]=src[u];m[cy-h:cy+h+1,cx-h:cx+h+1]=False
    a[Y0:Y1,X0:X1]=A
def planefill(x0,y0,x1,y1,inmask,ring=8,fe=8,crisp=()):
    """smooth surface (wall/lid/packet face): LSQ colour plane from clean ring + fine grain, feathered except on 'crisp' sides"""
    Y0,Y1,X0,X1=y0-ring,y1+ring,x0-ring,x1+ring;yy,xx=np.mgrid[Y0:Y1,X0:X1];sub=a[Y0:Y1,X0:X1]
    inR=inmask(xx,yy)&(xx>=x0)&(xx<x1)&(yy>=y0)&(yy<y1);hv=cv2.cvtColor(np.clip(sub,0,255).astype(np.uint8),cv2.COLOR_RGB2HSV);cl=~inR&inmask(xx,yy)&(hv[...,0]>60)&(hv[...,0]<95)&(hv[...,1]>40)
    co,*_=np.linalg.lstsq(np.stack([np.ones(cl.sum()),xx[cl],yy[cl]],1),sub[cl],rcond=None)
    F=np.stack([np.ones_like(xx),xx,yy],-1).astype(np.float32)@co+rng.normal(0,1.0,sub.shape)
    d=[yy-y0,x1-xx,y1-yy,xx-x0];d=[v for k,v in zip('tRbl',d) if k not in crisp]
    w=(np.clip(np.minimum.reduce(d)/fe,0,1) if d else 1.0)*inR;sub[:]=F*w[...,None]+sub*(1-w[...,None])
# 3) top-right cookie right-edge streak: cookie outline ellipse (crisp) + inner cell-wall face plane, wall rim / right wall edge untouched
ell=lambda xx,yy:((xx-2316)/54.)**2+((yy-1738)/48.)**2>1
rim=lambda xx:1683+(xx-2340)*0.34
planefill(2340,1692,2411,1754,lambda xx,yy:ell(xx,yy)&(xx<2411)&(yy>rim(xx)+3),fe=4,crisp='lRt')
# continue the wall rim line: clone the sharp rim segment along its own direction (+40,+14)
yy,xx=np.mgrid[1680:1718,2360:2411];bm=(np.abs(yy-rim(xx))<5).astype(np.float32);bm=cv2.GaussianBlur(bm,(0,0),1.0)[...,None]
a[1680:1718,2360:2411]=a[1666:1704,2320:2371]*bm+a[1680:1718,2360:2411]*(1-bm)
# 4) chocolate cookie right edge -> packet. packet left edge line E: (2342,1817)-(2322,1865)-(2290,1920)
E=np.array([(2346,1800),(2342,1817),(2322,1865),(2290,1922)])
def ex(y): return np.interp(y,E[:,1],E[:,0])
polyA=[(2292,1806)]+[(int(ex(y))-2,y) for y in range(1806,1906,6)]+[(2290,1906)]
exemplar(polyA,P=11,R=100,cb=(2195,1785,2300,1905))
# packet side: smooth packet face -> least-squares colour plane fitted on a clean ring, feathered into the face on top/right/bottom, crisp at the packet edge line
yy,xx=np.mgrid[1830:1945,2280:2380];e=np.round(ex(yy))
inR=(xx>=e)&(xx<2358)&(yy>=1842)&(yy<1932)
cl=(xx>=e+3)&~inR
X=np.stack([np.ones(cl.sum()),xx[cl],yy[cl]],1);sub=a[1830:1945,2280:2380]
co,*_=np.linalg.lstsq(X,sub[cl],rcond=None)
F=np.einsum('yxk,kc->yxc',np.stack([np.ones_like(xx),xx,yy],-1).astype(np.float32),co)+rng.normal(0,1.0,sub.shape)
w=np.clip(np.minimum.reduce([yy-1842,2358-xx,1932-yy])/10,0,1)*inR
sub[:]=F*w[...,None]+sub*(1-w[...,None])
# 5) lid (right-side whitish smear): plane fill
planefill(2380,1580,2446,1630,lambda xx,yy:np.ones_like(xx,bool),fe=10)
# 5b) lid whitish smear: clone flat lid from 70px left
sm=np.zeros((H,W),np.uint8);cv2.fillPoly(sm,[np.array([(2358,1580),(2420,1580),(2420,1604),(2358,1604)],np.int32)],1)
sm=cv2.GaussianBlur(sm.astype(np.float32),(0,0),1.5)[...,None];sh=np.roll(a,70,1)
a=sh*sm+a*(1-sm)
Image.fromarray(np.clip(a,0,255).astype(np.uint8)).save('promo_ex01_p6.png')
