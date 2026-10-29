import test from 'node:test';
import assert from 'node:assert/strict';
import {modeOf,turnRequest,mergeAgent} from './workspace-modes.mjs';
test('permission modes are explicit; plan and team carry instructions and commands remain intact',()=>{
 assert.equal(modeOf('bad'),'manual');assert.deepEqual(turnRequest('hello','manual'),{message:'hello',mode:'manual'});
 assert.equal(turnRequest('hello','bypass').mode,'bypass');assert.equal(turnRequest('hello','plan').mode,'plan');assert.match(turnRequest('hello','plan').message,/수정하거나 구현을 실행하지/);
 const team=turnRequest('할 일','team');assert.equal(team.mode,'bypass');assert.match(team.message,/subagent/);assert.ok(team.message.endsWith('할 일'));
 assert.deepEqual(turnRequest('/compact','team'),{message:'/compact',mode:'bypass'});
});
test('agent events update real rows without duplicate agents',()=>{
 const agents=[];mergeAgent(agents,{id:'one',name:'조사',status:'queued'});mergeAgent(agents,{id:'one',status:'completed'});mergeAgent(agents,null);
 assert.equal(agents.length,1);assert.equal(agents[0].status,'completed');assert.equal(agents[0].name,'조사');
});
