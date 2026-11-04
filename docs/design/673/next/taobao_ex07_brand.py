# 643 taobao-product ex07: replace gold brand REVENT with our own SOLVAIR (no dryer brand elsewhere in set; ex08 has no text). $0 local.
import sys,numpy as np
from PIL import Image,ImageDraw,ImageFont
p=sys.argv[1];im=Image.open(p).convert('RGB');a=np.array(im).astype(float)
x0,y0,x1,y1=74,796,264,846
L=a[y0:y1,x0-4];R=a[y0:y1,x1+1];t=np.linspace(0,1,x1-x0)[None,:,None]
a[y0:y1,x0:x1]=L[:,None]*(1-t)+R[:,None]*t
im=Image.fromarray(a.astype(np.uint8));d=ImageDraw.Draw(im)
f=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',41,index=0)
d.text((80,838),'SOLVAIR',font=f,fill=(245,245,245),anchor='ls')
im.save(sys.argv[2],'WEBP',quality=90)
