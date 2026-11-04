# poster4 / poster6 smear repair: normalized-convolution fill (smooth, no streaks) + fine grain
from PIL import Image
import numpy as np,cv2
a=np.array(Image.open('promo_ex01_lens.png').convert('RGB')).astype(np.float32)
def fill(a,boxes,sig=28,fe=10):
    m=np.zeros(a.shape[:2],np.float32)
    for x0,y0,x1,y1 in boxes: m[y0:y1,x0:x1]=1
    k=1-m;num=cv2.GaussianBlur(a*k[...,None],(0,0),sig);den=cv2.GaussianBlur(k,(0,0),sig)[...,None]+1e-4
    f=num/den+np.random.default_rng(7).normal(0,2.0,a.shape)
    w=cv2.GaussianBlur(m,(0,0),fe)[...,None];w=np.clip(w*1.6,0,1)
    return a*(1-w)+f*w
# poster6: top-left cookie streaks, box-lid streaks, bottom-right speck
a=fill(a,[(1845,1455,2100,1528),(2245,1520,2430,1725),(2490,2090,2540,2140)])
# poster4: left wall streaks, bottom floor streaks
a=fill(a,[(100,1445,335,1570),(50,1893,320,1952),(128,2105,440,2192)],sig=22)
a=np.clip(a,0,255).astype(np.uint8)
# poster4 sofa: leftover orange specks -> slate (recolour miss)
h=cv2.cvtColor(a,cv2.COLOR_RGB2HSV);yy,xx=np.mgrid[0:a.shape[0],0:a.shape[1]]
s=(xx>90)&(xx<540)&(yy>1430)&(yy<1700)&(h[...,0]<22)&(h[...,1]>60)
h[...,0]=np.where(s,105,h[...,0]);h[...,1]=np.where(s,(h[...,1]*0.35).astype(np.uint8),h[...,1])
a=cv2.cvtColor(h,cv2.COLOR_HSV2RGB)
Image.fromarray(a).save('promo_ex01_fixed.png')
