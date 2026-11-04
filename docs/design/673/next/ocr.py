import sys,json
from rapidocr_onnxruntime import RapidOCR
o=RapidOCR()
for f in sys.argv[1:]:
    r,_=o(f);r=r or []
    print('##',f);[print(json.dumps([[int(p[0]),int(p[1])] for p in b[0]][::2]),b[1],b[2]) for b in r]
