import test from 'node:test';
import assert from 'node:assert/strict';
import {defaults,validateGeneration,generationSampling} from '../strata/apps/host/server/workspace-generation.mjs';
import {shapeBody} from '../strata/apps/host/server/agent/llm-shape.mjs';
test('settings reach model body without leaking internal keys or changing tool schemas',()=>{
 const tools=[{type:'function',function:{name:'read'}}];
 const body={temperature:1,messages:[{role:'user',content:'hello'}],tools};
 const result=shapeBody(body,{sampling:generationSampling({...defaults,temperature:0.3,logit_bias:{'123':-5}})});
 assert.equal(result.temperature,0.3);assert.deepEqual(result.logit_bias,{'123':-5});assert.match(result.messages[0].content,/한국어/);assert.equal(result.tools,tools);
 assert.equal('workspace_settings' in result,false);assert.equal('workspace_language' in result,false);assert.equal(body.messages.length,1);
});
test('invalid bias and sampling are rejected, old expert precedence remains',()=>{
 for(const value of [{temperature:NaN},{top_k:1.2},{logit_bias:{'-1':0}},{logit_bias:{'3':101}},{logit_bias:[]}])assert.throws(()=>validateGeneration({...defaults,...value}));
 assert.equal(shapeBody({temperature:1},{sampling:{temperature:0.2}}).temperature,1);
});
