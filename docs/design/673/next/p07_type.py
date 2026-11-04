from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np
B='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc';R='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
GOLD=(222,184,124);GREY=(127,128,123)
def pager(d,cy,active,n=5,cx=960,sp=21,r=6):
    for i in range(n):
        x=cx+sp*(i-(n-1)/2);d.ellipse((x-r,cy-r,x+r,cy+r),fill=GOLD if i==active else GREY)
im=Image.open('p07_base.png').convert('RGB')
# soft left darkening for legibility
a=np.array(im).astype(float);w=np.clip(1-np.arange(1920)/700,0,1)[None,:,None]*0.35;a*=1-w;im=Image.fromarray(a.astype('uint8'))
d=ImageDraw.Draw(im)
f=lambda p,s:ImageFont.truetype(p,s)
t="QUIET PRINCIPLES";x=70
for ch in t: # letter-spaced small caps
    d.text((x,64),ch,font=f(B,26),fill=(225,220,205));x+=d.textlength(ch,font=f(B,26))+6
d.line((70,108,170,108),fill=GOLD,width=2)
items=[('01','静','少即是多，留白安放心绪'),('02','茶','一壶慢煮，时间随之放缓'),('03','书','几册旧书，与自己对话'),('04','窗','山色入窗，四季皆可观')]
y=600
for n,k,c in items:
    d.text((70,y+6),n,font=f(R,22),fill=GOLD);d.text((115,y-8),k,font=f(B,44),fill=(235,230,215));d.text((180,y+6),c,font=f(R,24),fill=(200,196,185));y+=82
d.text((50,999),'03/05',font=f(R,24),fill=(200,196,185))
pager(d,1028,2)
im.save('p07_final.png')
