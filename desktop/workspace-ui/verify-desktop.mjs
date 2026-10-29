import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtempSync,readFileSync,existsSync } from 'node:fs';
import { resolve,join } from 'node:path';
import { runDesktop,setDesktopEnabled } from '../strata/apps/host/server/agent/desktop-control.mjs';
const dir=mkdtempSync(resolve('.ram2vram-desktop/test-temp/desktop-live-'));
const output=join(dir,'result.txt');
const fixture=spawn('powershell.exe',['-NoProfile','-File',resolve('desktop/workspace-ui/desktop-fixture.ps1'),output],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let fixtureError='';fixture.stderr.on('data',c=>fixtureError+=c);
try{
 setDesktopEnabled(dir,true);let window;
 for(let n=0;n<8&&!window;n++){await new Promise(r=>setTimeout(r,500));const rows=(await runDesktop(dir,{action:'windows'})).windows;window=rows.find(w=>w.pid===fixture.pid&&w.title==='RAM2VRAM Synthetic Desktop Test');if(n===7&&!window)console.log({count:rows.length,fixturePid:fixture.pid,matches:rows.filter(w=>w.title==='RAM2VRAM Synthetic Desktop Test')});}
 assert.ok(window,`Synthetic window opened: ${fixtureError}`);const target={windowId:window.windowId,pid:window.pid};
 const run=async(action,extra={})=>{try{return await runDesktop(dir,{...target,action,...extra});}catch(e){throw new Error(`${action}: ${e.message}`);}};
 await run('focus');const tree=await run('inspect');assert.ok(tree.elements.length>0);
 const input=tree.elements.find(e=>e.type==='ControlType.Edit')??tree.elements.find(e=>e.name===''&&e.bounds.width>100);const button=tree.elements.find(e=>e.name==='Synthetic save');assert.ok(input&&button,JSON.stringify(tree));
 const capture=await run('screenshot');assert.equal(Buffer.from(capture.image,'base64').subarray(1,4).toString(),'PNG');
 await run('click',{x:Math.round(input.bounds.x+10),y:Math.round(input.bounds.y+10),button:'left'});
 await run('type',{text:'한글 synthetic 123'});await run('key',{key:'HOME'});await run('key',{key:'END'});
 try{await run('invoke',{elementId:button.elementId});}catch(e){assert.match(e.message,/does not support Invoke/);await run('click',{x:Math.round(button.bounds.x+10),y:Math.round(button.bounds.y+10)});}
 assert.equal(readFileSync(output,'utf8'),'한글 synthetic 123');
 await run('move',{x:100,y:100,width:600,height:350});await run('minimize');await run('restore');
 await run('scroll',{x:450,y:240,steps:1});await run('drag',{x:450,y:240,endX:470,endY:250});
 setDesktopEnabled(dir,false);await assert.rejects(run('type',{text:'must not type'}));
 setDesktopEnabled(dir,true);const stale=runDesktop(dir,{action:'windows'});setDesktopEnabled(dir,false);setDesktopEnabled(dir,true);await assert.rejects(stale,/stopped/);
 const concurrent=await Promise.allSettled([runDesktop(dir,{action:'windows'}),runDesktop(dir,{action:'windows'})]);assert.equal(concurrent.filter(r=>r.status==='fulfilled').length,1);assert.match(concurrent.find(r=>r.status==='rejected').reason.message,/busy/);
 assert.ok(existsSync(output));console.log('PASS: Windows list, UIA, PNG, click/type/key, invoke fallback, window controls, scroll/drag, stop generation, cross-process mutex');
}finally{setDesktopEnabled(dir,false);fixture.kill();}
