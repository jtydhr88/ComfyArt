from PIL import Image,ImageDraw,ImageFont,ImageFilter
B='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc';R='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
im=Image.open('promo_clean.png').convert('RGBA')
ov=Image.new('RGBA',im.size,(0,0,0,0));d=ImageDraw.Draw(ov)
F=lambda s,b=True:ImageFont.truetype(B if b else R,s,index=0)
def T(xy,t,s,c,b=True,sh=None):
    if sh: d.text((xy[0]+3,xy[1]+3),t,font=F(s,b),fill=sh)
    d.text(xy,t,font=F(s,b),fill=c)
# P1
T((560,40),'ORVA',64,'white');d.rectangle((40,770,600,1010),fill=(30,32,20,120))
T((60,780),'秋序上新',96,'white');T((62,920),'10.08 — 10.31',44,'white',False)
# P2
d.rounded_rectangle((925,590,1640,930),24,fill=(246,242,236,235))
T((910,40),'MIRO',54,(20,20,20));T((990,610),'MIRO 轻衫季',92,(20,20,20))
T((1050,760),'预售 10.12 开启',48,(30,30,30),False);T((1050,830),'付定立减 66 元',48,(30,30,30),False)
# P3
T((1790,20),'velle',180,(110,20,35));T((1960,190),'velle',180,(110,20,35))
d.rounded_rectangle((1880,930,2440,1030),20,fill=(110,20,35,230));T((1930,940),'限时立减 15',64,'white')
# P4
d.rectangle((0,1150,520,1440),fill=(40,44,52,150))
T((30,1170),'换个心情',110,'white');T((30,1305),'过冬！',110,'white')
d.rounded_rectangle((20,1950,560,2100),20,fill=(40,44,52,230));T((50,1985),'11 月 5 日 抢先购',64,'white')
# P5
T((960,1240),'KORAX × 年终盛典',70,'white');T((1080,1345),'全画幅新旗舰',54,(220,180,110),False)
# P6
d.rectangle((1760,1150,2550,1460),fill=(170,225,205,200))
T((1800,1170),'黄油小饼',150,(80,45,25));T((1805,1350),'CRUMBO',80,(80,45,25))
d.rounded_rectangle((1800,1990,2300,2130),20,fill=(80,45,25,235));T((1840,2020),'满 199 减 30',68,'white')
im=Image.alpha_composite(im,ov).convert('RGB');im.save('promo_ex01.png');im.resize((1280,1107)).save('pf_v.jpg')
