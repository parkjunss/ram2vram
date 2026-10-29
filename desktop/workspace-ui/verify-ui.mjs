import { chromium } from '../strata/apps/host/node_modules/playwright-core/index.mjs';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const output = join(here, '../../.ram2vram-desktop/logs/workspace-ui');
await mkdir(output, {recursive:true});
const model = {model:'iq2_xs',model_name:'Qwen3.8-Flash-Next IQ2_XS',ready:true,visionPrepared:true,visionEnabled:true,visionDevice:'cpu'};
const native = {installed:{models:[model]},instances:[{id:'fixture-model',model:'iq2_xs',label:model.model_name,status:'ready',metrics:{hardware:{ram_used:40*1024**3,ram_total:64*1024**3,gpu_mem_used:12*1024**3,gpu_mem_total:16*1024**3},engine:{expert_cache_mib:9318},requests:[{decode_tok_s:31.5}]}}]};
let decision, requested, release, folder=null, stopped=false;
native.instances[0].vision=true;
let nativeRequest;
let generation={temperature:0.6,top_p:0.95,top_k:40,max_tokens:4096,korean:true,logit_bias:{}};
let contextLimit=32768, contextRequest, compactCalls=0;
let desktopEnabled=false;
let skills=[{id:'workspace-research',name:'웹 조사',description:'출처 확인',body:'출처를 확인한다.',enabled:true,source:'bundled'}];
const json=(res,data)=>{res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(data));};
const server=createServer(async(req,res)=>{
  try {
    const url=new URL(req.url,'http://localhost'); let body=''; for await(const chunk of req) body+=chunk;
    const data=body?JSON.parse(body):{};
    if(url.pathname==='/api/native') return json(res,native);
    if(url.pathname==='/api/native/operations'){nativeRequest=data;if(data.args.vision!==undefined){model.visionEnabled=data.args.vision!=='no';model.visionDevice=data.args.vision;}native.instances[0].vision=model.visionEnabled;native.jobs=[{id:'vision-job',state:'done'}];return json(res,{id:'vision-job'});}
    if(url.pathname==='/api/workspace/desktop'){if(req.method==='POST')desktopEnabled=data.enabled;return json(res,{supported:true,enabled:desktopEnabled});}
    if(url.pathname==='/api/workspace/desktop/read')return json(res,data.action==='windows'?{windows:[{windowId:'123',pid:456,title:'Synthetic window'}]}:{elements:[{name:'Synthetic button'}]});
    if(url.pathname==='/api/workspace/generation'){if(req.method==='POST')generation=data;return json(res,generation);}
    if(url.pathname==='/api/workspace/context'){if(req.method==='POST'){contextRequest=data;contextLimit=data.tokens;return json(res,{savedTokens:contextLimit,reloadNeeded:true});}return json(res,{savedTokens:contextLimit,appliedTokens:32768,context:{tokens:8000,window:32768},autoCompact:{enabled:true,triggerTokens:20071}});}
    if(url.pathname==='/api/skills'){if(req.method==='POST'){skills.push({...data,id:'my-fixture',source:'created'});return json(res,{id:'my-fixture',skills});}return json(res,skills);}
    if(url.pathname.startsWith('/api/skills/')){const id=url.pathname.split('/').pop();if(req.method==='DELETE')skills=skills.filter(s=>s.id!==id);else Object.assign(skills.find(s=>s.id===id),data);return json(res,skills);}
    if(url.pathname==='/api/workspaces') return json(res,{workspaces:[{id:'root',path:'F:\\RAM2VRAM'}]});
    if(url.pathname==='/api/chat/folder'){if(req.method==='POST')folder=data.path;return json(res,{folder:folder?{path:folder}:null});}
    if(url.pathname==='/api/chat/approval'){decision=data;json(res,{ok:true});release?.();return;}
    if(url.pathname==='/api/chat/stop'){stopped=true;release?.();return json(res,{ok:true});}
    if(url.pathname==='/api/chat/stream'){
      requested=data;res.writeHead(200,{'content-type':'application/x-ndjson'});
      const frame=v=>res.write(JSON.stringify(v)+'\n');frame({type:'start',agent:true});
      if(data.message.includes('모드 검증')){for(const status of ['queued','working','completed'])frame({type:'agent',agent:{id:'child-fixture',name:'합성 에이전트',description:'분담 작업',status}});frame({type:'delta',text:'모드 검증 완료'});frame({type:'done'});res.end();return;}
      if(data.message==='/compact'){compactCalls++;frame({type:'status',phase:'compacting'});frame({type:'delta',text:'이전 대화를 요약했습니다.'});frame({type:'done'});res.end();return;}
      if(data.message==='중지 테스트'){await new Promise(r=>release=r);frame({type:'done',cancelled:true});res.end();return;}
      frame({type:'delta',text:'안녕하세요. <img src=x onerror="globalThis.injected=1">\n'});
      frame({type:'agent-tool',tool:{id:'call-fixture',name:'write',state:'proposed',args:{file_path:'F:/synthetic.txt',content:'<script>bad()</script>'},preview:'F:/synthetic.txt',effect:'합성 파일 테스트'}});
      await new Promise(r=>release=r);
      frame({type:'agent-tool',tool:{id:'call-fixture',name:'write',state:decision?.decision==='approve'?'done':'denied',result:'Synthetic result'}});
      frame({type:'delta',text:'검증 완료. [공식 문서](https://docs.python.org/)\n```js\nconst safe = true;\n```'});frame({type:'done'});res.end();return;
    }
    const name=url.pathname.split('/').pop()||'index.html';
    if(!['index.html','workspace.css','workspace-settings.css','workspace.js','workspace-tools.mjs','workspace-history.mjs','workspace-modes.mjs','workspace-desktop.mjs','workspace-vision.mjs','workspace-core.mjs','manifest.json'].includes(name)){res.writeHead(404);res.end();return;}
    const mime=name.endsWith('.css')?'text/css':name.endsWith('.html')?'text/html':name.endsWith('.json')?'application/json':'text/javascript';
    res.writeHead(200,{'content-type':mime});res.end(await readFile(join(here,name)));
  }catch(error){res.writeHead(500);res.end(error.message);}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
  const page=await browser.newPage({viewport:{width:1440,height:920}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/workspace/index.html`);
  await page.waitForFunction(()=>document.querySelector('#connection-text').textContent==='로컬 모델 연결됨');
  await page.locator('#desktop-enable').click();await page.waitForFunction(()=>document.querySelector('#desktop-enable').disabled);assert.equal(desktopEnabled,true);
  await page.locator('#desktop-open').click();await page.locator('#desktop-window option').waitFor({state:'attached'});await page.locator('#desktop-inspect').click();await page.waitForFunction(()=>document.querySelector('#desktop-tree').textContent.includes('Synthetic button'));await page.locator('#desktop-close').click();
  await page.locator('#desktop-stop').click();await page.waitForFunction(()=>!document.querySelector('#desktop-enable').disabled);assert.equal(desktopEnabled,false);
  await page.screenshot({path:join(output,'welcome.png'),fullPage:true});
  await page.locator('#generation-settings').click();
  await page.locator('#setting-temperature').fill('0.3');
  await page.locator('#setting-logit_bias').fill('{"123":-5}');
  await page.locator('#settings-form button[type=submit]').click();
  await page.waitForFunction(()=>!document.querySelector('#settings-dialog').open);
  assert.equal(generation.temperature,0.3);assert.deepEqual(generation.logit_bias,{'123':-5});
  await page.locator('#context-settings').click();await page.locator('#context-limit').fill('24576');await page.locator('#context-form button[value=save]').click();
  await page.waitForFunction(()=>!document.querySelector('#context-dialog').open);assert.equal(contextRequest.tokens,24576);assert.equal(contextRequest.reload,false);
  await page.locator('#context-settings').click();await page.locator('#context-form button[value=reload]').click();await page.waitForFunction(()=>!document.querySelector('#context-dialog').open);assert.equal(nativeRequest.args.vision,undefined);assert.equal(model.visionEnabled,true);
  await page.locator('#skills-open').click();await page.locator('#skill-new').click();
  await page.locator('#skill-name').fill('합성 스킬');await page.locator('#skill-description').fill('테스트에서 사용');await page.locator('#skill-body').fill('합성 자료만 읽는다.');await page.locator('#skill-form button[type=submit]').click();
  await page.locator('.skill-row').filter({hasText:'합성 스킬'}).waitFor();
  let skillRow=page.locator('.skill-row').filter({hasText:'합성 스킬'});
  await skillRow.getByRole('button',{name:'활성 · 끄기',exact:true}).click();await skillRow.getByRole('button',{name:'비활성 · 켜기',exact:true}).waitFor();
  await skillRow.getByRole('button',{name:'편집',exact:true}).click();await page.locator('#skill-body').fill('수정된 지침');await page.locator('#skill-form button[type=submit]').click();await page.waitForFunction(()=>document.querySelector('#skill-form').hidden);assert.equal(skills.find(s=>s.id==='my-fixture').body,'수정된 지침');
  await skillRow.getByRole('button',{name:'삭제',exact:true}).click();await skillRow.getByRole('button',{name:'정말 삭제',exact:true}).click();await skillRow.waitFor({state:'detached'});
  await page.locator('#skills-close').click();
  assert.equal(await page.locator('#vision-mode').inputValue(),'cpu');
  await page.locator('#chat-images').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB1cAAAAASUVORK5CYII=','base64')});
  await page.waitForFunction(()=>document.querySelector('#image-draft').textContent.includes('synthetic.png'));
  await page.locator('#prompt').fill('UI 합성 검증');await page.locator('#send').click();
  await page.locator('.approve').waitFor();
  assert.equal(await page.locator('#messages img').count(),0,'Model HTML must be inert');
  assert.equal(await page.evaluate(()=>globalThis.injected),undefined);
  await page.screenshot({path:join(output,'approval.png'),fullPage:true});
  await page.locator('.approve').click();
  await page.waitForFunction(()=>document.querySelector('#stop').hidden);
  assert.equal(decision.sessionId,requested.sessionId);assert.equal(decision.toolId,'call-fixture');assert.equal(decision.decision,'approve');
  assert.equal(requested.nativeModelId,'fixture-model');assert.equal(requested.mode,'manual');
  assert.equal(requested.images.length,1);assert.equal(requested.images[0].name,'synthetic.png');
  assert.match(await page.locator('#messages').innerText(),/검증 완료/);
  assert.equal(await page.locator('#messages a').getAttribute('rel'),'noopener noreferrer');
  await page.locator('#choose-folder').click();await page.locator('#folder-input').fill('F:\\synthetic');await page.locator('#folder-form button[type=submit]').click();
  await page.waitForFunction(()=>document.querySelector('#folder-path').textContent==='F:\\synthetic');
  await page.waitForFunction(()=>JSON.parse(localStorage.getItem('ram2vram.workspace.v1')).sessions[0].busy===false);
  await page.reload();await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('검증 완료'));
  await page.locator('#prompt').fill('보존할 초안');await page.locator('#compact-now').click();await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('이전 대화를 요약했습니다.'));assert.equal(compactCalls,1);assert.equal(await page.locator('#prompt').inputValue(),'보존할 초안');
  await page.evaluate(()=>{const box=document.querySelector('#messages');for(let i=0;i<80;i++){const p=document.createElement('p');p.textContent='긴 대화 스크롤 검증 '+i;box.append(p);}});
  const scroll=await page.evaluate(()=>{const el=document.querySelector('#conversation');el.scrollTop=el.scrollHeight;return {top:el.scrollTop,overflow:el.scrollHeight>el.clientHeight,composer:document.querySelector('#composer').getBoundingClientRect().bottom<=innerHeight};});
  assert.equal(scroll.overflow,true);assert.ok(scroll.top>0);assert.equal(scroll.composer,true);
  await page.locator('#conversation').hover();await page.mouse.wheel(0,-500);
  await page.waitForFunction(top=>document.querySelector('#conversation').scrollTop<top,scroll.top);
  await page.locator('#new-chat').click();await page.locator('#prompt').fill('중지 테스트');await page.locator('#send').click();
  await page.locator('#stop').waitFor();await page.locator('#stop').click();
  await page.waitForFunction(()=>document.querySelector('#stop').hidden);assert.equal(stopped,true);
  await page.setViewportSize({width:900,height:600});await page.screenshot({path:join(output,'compact.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No horizontal overflow');
  const backup={active:'restore-fixture',sessions:[{id:'restore-fixture',title:'복구 검증',created:Date.now(),messages:[{role:'user',text:'복구된 합성 기록'}],busy:false}]};
  await page.locator('#history-file').setInputFiles({name:'backup.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(backup))});
  await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('복구된 합성 기록'));
  await page.reload();await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('복구된 합성 기록'));
  for(const mode of ['plan','bypass','team']){
    await page.locator('#mode').selectOption(mode);
    await page.locator('#prompt').fill('모드 검증');await page.locator('#send').click();
    await page.waitForFunction(()=>document.querySelector('#stop').hidden);
    assert.equal(requested.mode,mode==='team'?'bypass':mode);
    if(mode==='plan')assert.match(requested.message,/계획/);
    if(mode==='team')assert.match(requested.message,/subagent/);
    assert.equal(await page.locator('.agent-card').count(),['plan','bypass','team'].indexOf(mode)+1);
    await page.reload();await page.waitForFunction(()=>document.querySelector('#connection-text').textContent==='로컬 모델 연결됨');
    assert.equal(await page.locator('#mode').inputValue(),mode);
  }
  assert.match(await page.locator('.agent-card').last().innerText(),/완료/);
  await page.locator('#new-chat').click();assert.equal(await page.locator('#mode').inputValue(),'manual');
  await page.locator('#vision-mode').selectOption('no');await page.locator('#vision-apply').click();await page.waitForFunction(()=>document.querySelector('#chat-images').disabled);assert.equal(nativeRequest.args.vision,'no');
  assert.deepEqual(errors,[]);console.log('PASS: rendering, safe text, streaming, approval identity, folder, persistence, cancellation, compact layout, history import, mode requests and persistence, agent lifecycle');
}finally{await browser.close();server.close();}
