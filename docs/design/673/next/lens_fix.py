# poster5 lens: restore gold lens texture, erase only glyph pixels (no box inpaint)
from PIL import Image
import numpy as np,cv2
g=np.array(Image.open('gold_ex01.png').convert('RGB'));f=np.array(Image.open('promo_ex01.png').convert('RGB'))
cx,cy=1395,1770
yy,xx=np.mgrid[0:g.shape[0],0:g.shape[1]];r=np.hypot(xx-cx,yy-cy)
V=cv2.cvtColor(g,cv2.COLOR_RGB2HSV)[...,2].astype(int)
m=np.zeros(g.shape[:2],np.uint8)
ring=(r>108)&(r<152)&(V>140);m[ring]=255
bx=(xx>1425)&(xx<1560)&(yy>1540)&(yy<1580)&(V<120);m[bx]=255
rf=(xx>1240)&(xx<1560)&(yy>1930)&(yy<2060)&(V>70);m[rf]=255
m=cv2.dilate(m,np.ones((5,5),np.uint8))
c=cv2.inpaint(g,m,4,cv2.INPAINT_TELEA)
cv2.imwrite('/tmp/lensmask.png',m)
reg=((r<215)|((xx>1230)&(xx<1600)&(yy>1535)&(yy<1700))|((xx>1220)&(xx<1580)&(yy>1930)&(yy<2040))).astype(np.float32)
reg=cv2.GaussianBlur(reg,(0,0),12)[...,None]
o=(c*reg+f*(1-reg)).astype(np.uint8)
Image.fromarray(o).save('promo_ex01_lens.png')
Image.fromarray(np.concatenate([f[1400:2050,1100:1700],o[1400:2050,1100:1700]],1)).save('lens_LR.jpg',quality=90)
