# promo ex02 (app examples/01): add gold's festival date "11.11" (glyphs copied from gold) before our 当天发货, gold-style layout. $0.
import sys
from PIL import Image,ImageDraw,ImageFont
src,gold,out=sys.argv[1:4]
im=Image.open(src).convert('RGB');g=Image.open(gold).convert('RGB');d=ImageDraw.Draw(im)
d.rectangle((60,1268,440,1362),fill=(255,255,255))           # our old 当天发货 line
im.paste(g.crop((52,1274,182,1342)),(56,1282))               # gold 11.11 glyphs (date only)
f=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc' if __import__('os').path.exists('/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc') else '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',58,index=0)
d.text((192,1316),'当天发货',font=f,fill=(10,10,10),anchor='lm')
im.save(out,'WEBP',quality=90)
