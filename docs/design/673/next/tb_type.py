from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np
B='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc';R='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
im=Image.open('tb_base.png').convert('RGB')
# soft scrim over the hero top (covers the pre-clean smear)
a=np.array(im).astype(float);m=np.zeros(a.shape[:2]);m[80:370,890:1540]=1
m=np.array(Image.fromarray((m*255).astype('uint8')).filter(ImageFilter.GaussianBlur(95))).astype(float)/255
blur=np.array(im.filter(ImageFilter.GaussianBlur(18))).astype(float)*0.55
a=a*(1-m[...,None])+blur*m[...,None];im=Image.fromarray(a.astype('uint8'))
d=ImageDraw.Draw(im);cx=1215
ft=ImageFont.truetype(B,104);t='松弛一身';w=d.textlength(t,font=ft)
sh=Image.new('L',im.size,0);ImageDraw.Draw(sh).text((cx-w/2+3,140+4),t,font=ft,fill=110);sh=sh.filter(ImageFilter.GaussianBlur(6))
im.paste((0,0,0),mask=sh);d=ImageDraw.Draw(im)
d.text((cx-w/2,140),t,font=ft,fill=(255,255,255))
fs=ImageFont.truetype(R,26);s='高腰阔腿西装裤 · 羊毛混纺';w2=d.textlength(s,font=fs);d.text((cx-w2/2,282),s,font=fs,fill=(245,242,235))
im.save('taobao_final.png')
