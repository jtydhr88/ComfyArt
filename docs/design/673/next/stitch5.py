from PIL import Image,ImageDraw,ImageFont
import numpy as np,cv2,json
B='/workspace/wt673a/docs/design/673/batch/'
GOLD=(222,184,124);GREY=(127,128,123)
def repager(im,cy,active):
    a=np.array(im);m=np.zeros(a.shape[:2],np.uint8);m[cy-10:cy+11,900:1020]=255
    a=cv2.inpaint(a,m,5,cv2.INPAINT_TELEA);im=Image.fromarray(a);d=ImageDraw.Draw(im)
    for i in range(5):
        x=960+21*(i-2);d.ellipse((x-6,cy-6,x+6,cy+6),fill=GOLD if i==active else GREY)
    return im
FNT=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',24)
def num(im,t,y=999,clear=False):
    if clear:
        a=np.array(im);m=np.zeros(a.shape[:2],np.uint8);m[996:1028,46:120]=255;im=Image.fromarray(cv2.inpaint(a,m,5,cv2.INPAINT_TELEA))
    ImageDraw.Draw(im).text((50,y),t,font=FNT,fill=(200,196,185));return im
# page number = position in the 5-page long image; 5 pager dots on every page
p01=num(repager(Image.open(B+'ppt-p01.webp').convert('RGB'),1028,0),'01/05')
p02=num(repager(Image.open(B+'ppt-p02.webp').convert('RGB'),1028,1),'02/05',clear=True)
p07=Image.open('p07_final.png').convert('RGB')  # 03/05 drawn in p07_type.py
p08=num(repager(Image.open(B+'ppt-p08.webp').convert('RGB'),1030,3),'04/05',y=1010)
p10=num(repager(Image.open(B+'ppt-p10.webp').convert('RGB'),1028,4),'05/05')
pages=[p01,p02,p07,p08,p10]
for n,p in zip(['p01','p02','p07','p08','p10'],pages): p.save(f'page_{n}.png')
s=np.concatenate([np.array(p) for p in pages]).astype(float)
J=[1047*i for i in range(1,5)]
y=np.arange(s.shape[0]);f=np.minimum(np.clip(np.abs(y-J[0])/96,0,1),np.clip(np.abs(y-J[1])/96,0,1))[:,None,None]
s=12+(s-12)*f
for j in J: s[j-2:j+2]=12
s=np.clip(s,0,255).astype('uint8');Image.fromarray(s).save('stitched5.png');print(s.shape)
L=s.mean(2);rows=L.mean(1);rep=[]
for j in J:
    dlt=abs(rows[j-3]-rows[j+2]);rep.append({'join':int(j),'lum_diff':round(float(dlt),2),'pass':bool(dlt<18)})
rep={'joins':rep,'row_min':round(float(rows.min()),2),'row_max':round(float(rows.max()),2),'rows_ok':bool(rows.min()>=5 and rows.max()<=250)}
print(json.dumps(rep));json.dump(rep,open('seams5.json','w'),indent=1)
# seams sheet
strips=[s[j-120:j+120] for j in J];sheet=np.concatenate([np.pad(x,((0,8),(0,0),(0,0)),constant_values=255) for x in strips])
Image.fromarray(sheet).resize((960,sheet.shape[0]//2)).save('seams5.jpg',quality=88)
