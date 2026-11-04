import sys
from PIL import Image,ImageDraw,ImageFont
g,o,out=sys.argv[1:4];G=Image.open(g).convert('RGB');O=Image.open(o).convert('RGB').resize(G.size)
h=min(1400,G.height);s=h/G.height;G=G.resize((int(G.width*s),h));O=O.resize(G.size)
c=Image.new('RGB',(G.width*2+20,h+60),'white');c.paste(G,(0,60));c.paste(O,(G.width+20,60))
d=ImageDraw.Draw(c);f=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',36)
d.text((10,8),'GOLD',font=f,fill='black');d.text((G.width+30,8),'OURS',font=f,fill='black');c.save(out,quality=88)
