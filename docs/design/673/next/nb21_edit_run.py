import os,json,time,urllib.request,subprocess,sys
K=os.environ['WAVESPEED_API_KEY'];H={'Authorization':'Bearer '+K}
B='https://api.wavespeed.ai/api/v3'
def req(url,data=None):
    r=urllib.request.Request(url,data=data,headers={**H,'Content-Type':'application/json'});return json.load(urllib.request.urlopen(r,timeout=120))
def bal(): return float(req(B+'/balance')['data']['balance'])
name,src,tag=sys.argv[1],sys.argv[2],sys.argv[3]
P=json.load(open('prompts.json'))
b0=bal()
if b0<20: print('STOP balance',b0);sys.exit(2)
up=subprocess.run(['curl','-s','-H','Authorization: Bearer '+K,'-F','file=@'+src,B+'/media/upload/binary'],capture_output=True,text=True).stdout
img=json.loads(up)['data']['download_url']
j=req(B+'/google/nano-banana-2.1/edit',json.dumps({'images':[img],'prompt':P[name],'resolution':'1k','output_format':'png'}).encode())
rid=j['data']['id']
for _ in range(150):
    time.sleep(3);g=req(B+f'/predictions/{rid}/result')['data']
    if g['status'] in('completed','failed','cancelled','timeout'):break
if g['status']=='completed': urllib.request.urlretrieve(g['outputs'][0],f'out_{name}_{tag}.png')
time.sleep(3);b1=bal()
rec=dict(slot=name,tag=tag,id=rid,status=g['status'],err=g.get('error'),before=b0,after=b1,cost=round(b0-b1,4),t=time.strftime('%H:%M:%S'))
print(json.dumps(rec,ensure_ascii=False));open('log.jsonl','a').write(json.dumps(rec,ensure_ascii=False)+'\n')
