# #673 promo ex01: restore platform/festival elements (双11/天猫/淘宝) per Angela's exemption. $0, local only.
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np,cv2
B='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
F=lambda s:ImageFont.truetype(B,s,index=0)
G=Image.open('/workspace/next673/gold_ex01.png').convert('RGB');ga=np.array(G)
O=Image.open('promo-ex01.webp').convert('RGB');a=np.array(O)
def red_mask(p):
    h=cv2.cvtColor(p,cv2.COLOR_RGB2HSV);return (((h[...,0]<10)|(h[...,0]>170))&(h[...,1]>120)&(h[...,2]>110)).astype(np.uint8)
def white_mask(p): return (p.min(2)>200).astype(np.uint8)
def paste(box,mfn,dst,scale=1.0,grow=1):
    x0,y0,x1,y1=box;p=ga[y0:y1,x0:x1];m=mfn(p)
    ys,xs=np.nonzero(m);p=p[ys.min():ys.max()+1,xs.min():xs.max()+1];m=m[ys.min():ys.max()+1,xs.min():xs.max()+1]
    if scale!=1:
        sz=(int(p.shape[1]*scale),int(p.shape[0]*scale));p=cv2.resize(p,sz,interpolation=cv2.INTER_AREA);m=cv2.resize(m.astype(np.float32),sz)
    m=cv2.dilate((m>0.3).astype(np.uint8),np.ones((3,3)),iterations=grow).astype(np.float32);m=cv2.GaussianBlur(m,(0,0),0.8)[...,None]
    X,Y=dst;h,w=p.shape[:2];r=a[Y:Y+h,X:X+w].astype(np.float32)
    a[Y:Y+h,X:X+w]=(r*(1-m)+p*m).astype(np.uint8);return w,h
# cell1 ORVA: white 双11 logo top-right (gold 679,31-775,86), shifted right of ORVA
# move ORVA to top-left like gold VANT
mk=np.zeros(a.shape[:2],np.uint8);mk[45:130,555:745]=255;mk[100:140,25:70]=255;a=cv2.inpaint(a,mk,7,cv2.INPAINT_TELEA)
im=Image.fromarray(a);ImageDraw.Draw(im).text((36,26),'ORVA',font=F(58),fill='white');a=np.array(im)
paste((670,25,785,92),white_mask,(679,31),1.0)
# cell2 MIRO: divider + red 双11 (gold header right part)
x=1137;paste((1320,20,1430,85),red_mask,(1090,58),1.0)
a[62:104,1072:1074]=(60,60,60)
# cell5 KORAX: erase 年终盛典, put red 双11 logo (gold LUMVEX×双11)
im=Image.fromarray(a);d=ImageDraw.Draw(im);wk=d.textlength('KORAX × ',font=F(70))
mk=np.zeros(a.shape[:2],np.uint8);mk[1245:1340,int(960+wk)-4:1600]=255
a=cv2.inpaint(np.array(im),mk,7,cv2.INPAINT_TELEA)
paste((1400,1225,1580,1325),red_mask,(int(960+wk)+6,1258),1.0)
# cell5 bottom: 淘宝 + 天猫 icons (gold 1005-1245,2078-2135)
def icon_mask(p):
    h=cv2.cvtColor(p,cv2.COLOR_RGB2HSV);m=((h[...,1]>110)&(h[...,2]>120))|(p.min(2)>190)
    m=cv2.morphologyEx(m.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((9,9)));return m
paste((1000,2075,1236,2138),icon_mask,(1010,2080),1.0,0)
im=Image.fromarray(a);d=ImageDraw.Draw(im)
# cell3: 双11限时立减 15 (same bar/colour/font)
bar=tuple(int(v) for v in a[980,1900]);d.rounded_rectangle((1880,930,2440,1030),20,fill=bar)
t='双11限时立减 15';s=64
while d.textlength(t,font=F(s))>500: s-=2
d.text((1880+(560-d.textlength(t,font=F(s)))/2,980-s*0.62),t,font=F(s),fill='white')
# cell4: 双11狂欢购 header line inside the dark box, gold position
d.text((36,1150),'ARDEN  |  双11狂欢购',font=F(28),fill='white')
# cell4 date: 11.11 0点抢先购 (PM)
d.rounded_rectangle((20,1950,560,2100),20,fill=(40,44,52));t='11.11 0点抢先购';d.text((20+(540-d.textlength(t,font=F(64)))/2,1985),t,font=F(64),fill='white')
# cell1 search bar (ours shop name)
d.rounded_rectangle((70,1030,520,1080),25,outline='white',width=3);d.ellipse((92,1043,114,1065),outline='white',width=3);d.line((111,1062,120,1071),fill='white',width=3)
d.text((132,1036),'上天猫搜索 ORVA 官方旗舰店',font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',28,index=0),fill='white')
RG=lambda s:ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',s,index=0)
# cell2 search bar text next to tmall cat head (ours shop name)
bw=tuple(int(v) for v in a[984,1300]);d.rectangle((1140,964,1450,994),fill=bw);d.rounded_rectangle((1063,958,1492,999),20,outline=(70,70,70),width=2)
d.line((1148,972,1148,992),fill=(70,70,70),width=2);d.text((1159,967),'MIRO官方旗舰店',font=RG(22),fill=(40,40,40))
# cell5 search bar: our own text
d.rounded_rectangle((1252,2080,1580,2134),27,fill=(250,250,250));d.ellipse((1528,2093,1552,2117),outline=(200,30,50),width=3);d.line((1549,2114,1557,2122),fill=(200,30,50),width=3)
d.text((1278,2088),'KORAX官方旗舰店',font=RG(26),fill=(30,30,30))
a=np.array(im)
# cell6: red 双11必买 starburst badge (gold shape/colour), redrawn locally; gold copy 满300减50 -> our 满199减30
im=Image.fromarray(a);med=tuple(int(v) for v in np.median(ga[1250:1300,2330:2400].reshape(-1,3),0))
S=4;R0,R1,N=72,62,20;cx,cy=2474,1232
big=Image.new('RGBA',(2*R0*S+8,2*R0*S+8),(0,0,0,0));bd=ImageDraw.Draw(big);c0=R0*S+4
import math
pts=[(c0+(R0 if k%2==0 else R1)*S*math.cos(math.pi*k/N),c0+(R0 if k%2==0 else R1)*S*math.sin(math.pi*k/N)) for k in range(2*N)]
bd.polygon(pts,fill=med+(255,))
for txt,fs,yy in (('双11必买',32,-20),):
    f=F(fs*S);w=bd.textlength(txt,font=f);bd.text((c0-w/2,c0+yy*S),txt,font=f,fill='white')
big=big.rotate(-12,resample=Image.BICUBIC).resize((2*R0+2,2*R0+2),Image.LANCZOS)
im.paste(big,(cx-R0-1,cy-R0-1),big)
im.save('promo-ex01.webp','WEBP',quality=90,method=6)
