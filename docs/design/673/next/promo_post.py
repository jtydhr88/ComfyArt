from PIL import Image,ImageDraw,ImageFilter,ImageFont
import numpy as np,cv2,json,subprocess
g=Image.open('gold_ex01.png').convert('RGB')
raw=Image.open('promo_raw.png').convert('RGB').resize((1707,1107),Image.LANCZOS)
m=Image.new('L',g.size,0);d=ImageDraw.Draw(m)
d.ellipse((170,0,640,430),fill=255);d.ellipse((1160,95,1330,285),fill=255)
m=m.filter(ImageFilter.GaussianBlur(30))
top=g.copy();top.paste(raw,(0,0))
im=Image.composite(top,g,m)
a=np.array(im)
# recolour: trench (poster1, grey coat) -> olive ; sofa (poster4) -> slate ; poster6 yellow -> mint
hsv=cv2.cvtColor(a,cv2.COLOR_RGB2HSV).astype(np.int32)
H,S,V=hsv[...,0],hsv[...,1],hsv[...,2]
yy,xx=np.mgrid[0:a.shape[0],0:a.shape[1]]
pm=np.zeros(a.shape[:2],np.uint8);cv2.fillPoly(pm,[np.array([(330,290),(560,290),(800,600),(800,1070),(300,1070),(110,700),(100,620),(300,560)])],1)
coat=(pm>0)&(S<60)&(V>60)&(V<200)&~((H>85)&(H<135))
coat_m=cv2.GaussianBlur(coat.astype(np.float32),(0,0),3)
olive=np.array([118,122,72],np.float32)
lum=(a.astype(np.float32).mean(2,keepdims=True)/130.0)
a=(a*(1-coat_m[...,None]*0.8)+np.clip(olive*lum,0,255)*coat_m[...,None]*0.8).astype(np.uint8)
hsv=cv2.cvtColor(a,cv2.COLOR_RGB2HSV)
sofa=(xx<810)&(yy>1550)&(yy<1900)&(xx>40)&(hsv[...,0]<22)&(hsv[...,1]>90)
hsv[...,0]=np.where(sofa,105,hsv[...,0]);hsv[...,1]=np.where(sofa,(hsv[...,1]*0.35).astype(np.uint8),hsv[...,1])
yel=(xx>1750)&(yy>1140)&(hsv[...,0]>=18)&(hsv[...,0]<=35)&(hsv[...,1]>120)
hsv[...,0]=np.where(yel,75,hsv[...,0]);hsv[...,1]=np.where(yel,(hsv[...,1]*0.45).astype(np.uint8),hsv[...,1])
a=cv2.cvtColor(hsv,cv2.COLOR_HSV2RGB)
# erase gold text from OCR boxes
boxes=json.load(open('gold_boxes.json'))
mk=np.zeros(a.shape[:2],np.uint8)
for (x0,y0),(x1,y1) in boxes: mk[max(0,y0-14):y1+14,max(0,x0-14):x1+14]=255
extra=[(1770,20,2560,380),(1300,1590,1570,1700),(1280,1800,1470,2010),(1010,2060,1110,2150),(1820,1990,1880,2140),(18,1250,510,1420),(1820,1190,2440,1530),(2280,1560,2460,1700),(2310,1880,2440,1990),(1300,1840,1360,1920),(1330,1600,1480,1680),(1090,2070,1440,2140)]
for x0,y0,x1,y1 in extra: mk[y0:y1,x0:x1]=255
a=cv2.inpaint(a,mk,7,cv2.INPAINT_TELEA)
Image.fromarray(a).save('promo_clean.png')
