# two-way OCR: list gold lines found in ours and our lines found in gold (substring >=2 chars, allowlist removed)
import sys,re
from rapidocr_onnxruntime import RapidOCR
from PIL import Image;import numpy as np
o=RapidOCR();AL=['双11','双十一','11.11','天猫','淘宝','淘','抖音','京东','618','TIME','狂欢','预售','礼遇季','专享','热卖']
def lines(p):
    im=Image.open(p).convert('RGB');out=[]
    for s in (1,2):
        a=im.resize((im.width*s,im.height*s))
        if max(a.size)>6000:a=a.resize((a.width*6000//max(a.size),a.height*6000//max(a.size)))
        r,_=o(np.array(a)[:,:,::-1]);out+=[x[1] for x in r or []]
    return sorted(set(out))
def norm(t):
    for w in AL:t=t.replace(w,' ')
    return re.sub(r'[\s/／·|｜:：,，.。>()（）\-]+',' ',t).strip()
ours,gold=lines(sys.argv[1]),lines(sys.argv[2])
def shared(A,B):
    hits=[]
    for a in A:
        for tok in norm(a).split():
            if len(tok)>=3 or (len(tok)>=2 and not tok.isascii()):
                if any(tok.upper() in norm(b).upper() for b in B): hits.append(tok)
    return sorted(set(hits))
print('## ours',sys.argv[1]);print(' | '.join(ours))
print('## gold',sys.argv[2]);print(' | '.join(gold))
print('OURS_IN_GOLD:',shared(ours,gold));print('GOLD_IN_OURS:',shared(gold,ours))
