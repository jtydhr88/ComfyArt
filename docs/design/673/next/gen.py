import os,sys,json,time,requests
sys.path.insert(0,'/workspace/ws');import ws
B=ws.B;H=ws.H
def bal(): return float(requests.get(B+'/balance',headers=H,timeout=20).json()['data']['balance'])
def run(src,prompt,out,ar):
    b0=bal()
    if b0<20: print('BALANCE<20 STOP');sys.exit(2)
    u=[ws.up(src)]
    r=requests.post(f'{B}/google/nano-banana-2.1/edit',headers=H,json={'images':u,'prompt':prompt,'output_format':'png','resolution':'1k','aspect_ratio':ar},timeout=60).json()
    ok=False;rid=None
    if r.get('code')==200:
        rid=r['data']['id']
        for _ in range(90):
            time.sleep(4);g=requests.get(f'{B}/predictions/{rid}/result',headers=H,timeout=30).json()['data']
            if g['status']=='completed': open(out,'wb').write(requests.get(g['outputs'][0],timeout=120).content);ok=True;break
            if g['status']=='failed': print('FAIL',g.get('error'));break
    else: print('ERR',{k:v for k,v in r.items() if k!='data'})
    time.sleep(3);b1=bal()
    rec=dict(out=out,id=rid,ok=ok,before=b0,after=b1,cost=round(b0-b1,6));print(json.dumps(rec),flush=True)
    open('calls.jsonl','a').write(json.dumps(rec)+'\n');return ok
if __name__=='__main__':
    j=json.load(open(sys.argv[1]));sys.exit(0 if run(j['src'],j['prompt'],j['out'],j['ar']) else 1)
