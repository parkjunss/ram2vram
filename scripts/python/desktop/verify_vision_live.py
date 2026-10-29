"""Reload CPU vision preserving settings, then test an image through the real Harness."""
import base64
import json
import time
import uuid
import urllib.request
from PIL import Image, ImageDraw, ImageFont
from runtime import STATE

BASE = 'http://127.0.0.1:47832'
def api(path, body=None, timeout=30):
    req=urllib.request.Request(BASE+path, data=json.dumps(body).encode() if body is not None else None,
                               headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)

def main():
    status=api('/api/agent/status')
    if status.get('activeTurns') or status.get('pendingApprovals'):
        raise RuntimeError('An existing chat is active; model reload was not started')
    before=api('/api/native')
    current=next(i for i in before['instances'] if i['model']=='iq2_xs' and i['status']=='ready')
    context=current['context']
    job=api('/api/native/operations',{'kind':'load','args':{'model':'iq2_xs','vision':'cpu','values':{'parallel':1}}})
    print('CPU vision model reload started',flush=True)
    for n in range(300):
        time.sleep(2)
        state=api('/api/native')
        found=next((j for j in state['jobs'] if j['id']==job['id']),{})
        if found.get('state')=='error':
            raise RuntimeError(found.get('error') or found.get('summary'))
        if found.get('state')=='done':
            break
        if n%10==0:print('Reload state: '+str(found.get('summary',found.get('state'))),flush=True)
    else:raise RuntimeError('Model reload timed out')
    instance=next(i for i in state['instances'] if i['model']=='iq2_xs' and i['status']=='ready')
    assert instance['vision'] is True
    assert instance['context']==context, 'Context changed unexpectedly'
    folder=STATE/'logs/vision';folder.mkdir(parents=True,exist_ok=True)
    code='V'+uuid.uuid4().hex[:5].upper()
    picture=Image.new('RGB',(800,400),'white');draw=ImageDraw.Draw(picture)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',96)
    draw.text((180,140),code,fill='black',font=font)
    draw.rectangle((40,40,130,130),fill='red');draw.ellipse((650,260,750,360),fill='blue')
    path=folder/'synthetic-vision.png';picture.save(path)
    data='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    body={'sessionId':'vision-check-'+uuid.uuid4().hex,'nativeModelId':instance['id'],'mode':'plan','thinking':'off',
          'message':'첨부 이미지 중앙에 적힌 영문과 숫자 코드를 그대로 읽어 주세요. 코드만 답하세요. 파일이나 다른 도구를 사용하지 마세요.',
          'images':[{'name':'synthetic-vision.png','url':data}]}
    req=urllib.request.Request(BASE+'/api/chat/stream',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    answer='';errors=[];done=False
    with urllib.request.urlopen(req,timeout=300) as response:
        for line in response:
            if not line.strip():continue
            frame=json.loads(line)
            if frame.get('type')=='delta':answer+=frame.get('text','')
            if frame.get('type')=='error':errors.append(frame.get('message') or frame.get('error'))
            if frame.get('type')=='done':done=True
    result={'expected':code,'answer':answer,'errors':errors,'done':done,'vision':instance['vision'],'context':instance['context']}
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    assert done and not errors and code in answer, 'Image recognition check failed'
    print('PASS: real Qwen image recognition through Harness; context preserved',flush=True)

if __name__=='__main__':main()
