import {chromium} from '../strata/apps/host/node_modules/playwright-core/index.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const base='http://127.0.0.1:47832';
const output=resolve('.ram2vram-desktop/logs/workspace-ui');await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
let created=null;
const skillName='작업 검증 '+Date.now();
const call=async(path,data,method)=>{const r=await fetch(base+path,{method:method||(data?'POST':'GET'),headers:{'content-type':'application/json'},body:data?JSON.stringify(data):undefined});const result=await r.json();if(!r.ok)throw new Error(JSON.stringify(result));return result;};
const before=await call('/api/workspace/context?model=iq2_xs');
try{
 const page=await browser.newPage({viewport:{width:1440,height:920}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/workspace/index.html');
 await page.waitForFunction(()=>!document.querySelector('#context-settings').disabled);
 await page.locator('#context-settings').click();await page.locator('#context-limit').fill('24576');await page.locator('#context-form button[value=reload]').click();
 await page.waitForFunction(()=>document.querySelector('#connection-text').textContent==='로컬 모델 연결됨',{}, {timeout:300000});
 await page.waitForFunction(()=>document.querySelector('#context-usage').textContent.includes('24,576'),{}, {timeout:30000});
 const changed=await call('/api/workspace/context?model=iq2_xs');assert.equal(changed.appliedTokens,24576);assert.equal(changed.savedTokens,24576);
 await page.locator('#skills-open').click();await page.locator('.skill-row').filter({hasText:'웹 조사와 출처 확인'}).waitFor();
 await page.screenshot({path:resolve(output,'skills-live.png'),fullPage:true});
 await page.locator('#skill-new').click();await page.locator('#skill-name').fill(skillName);await page.locator('#skill-description').fill('UI가 저장한 검증 지침을 확인할 때 사용');await page.locator('#skill-body').fill('합성 검증용 스킬입니다. 실제 사용자 파일은 읽지 않습니다.');await page.locator('#skill-form button[type=submit]').click();
 await page.waitForFunction(()=>document.querySelector('#skill-form').hidden);created=(await call('/api/skills')).find(s=>s.name===skillName)?.id;assert.ok(created);
 await page.locator('#skills-close').click();
 await page.locator('#prompt').fill('컨텍스트 검증용입니다. 도구를 쓰지 말고 한국어 한 문장으로 준비됐다고 답하세요.');await page.locator('#send').click();
 await page.waitForFunction(()=>document.querySelector('#stop').hidden,{}, {timeout:180000});assert.equal(await page.locator('.message-error').count(),0);
 await page.locator('#compact-now').click();await page.waitForFunction(()=>document.querySelector('#stop').hidden,{}, {timeout:180000});
 assert.match(await page.locator('#messages').innerText(),/요약|압축/);assert.equal(await page.locator('.message-error').count(),0);
 await page.screenshot({path:resolve(output,'context-live.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 await writeFile(resolve(output,'context-live-result.json'),JSON.stringify({changed,created,manualCompactText:await page.locator('.message.assistant').last().innerText()},null,2));
 console.log('PASS: actual context reload to 24576, built-in skills, Korean skill creation, model response, manual compact command');
}catch(error){console.error(error);throw error;}
finally{
 if(created)await call('/api/skills/'+encodeURIComponent(created),undefined,'DELETE');
 const restored=await call('/api/workspace/context',{model:'iq2_xs',tokens:before.savedTokens||32768,reload:true});
 console.log('Restore context job:',restored.job?.id);
 await browser.close();
}
