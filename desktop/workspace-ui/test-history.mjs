import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeHistory} from './workspace-history.mjs';
test('restore missing histories without removing current work or replacing a longer copy',()=>{
 const current=[{id:'new',title:'New',messages:[]},{id:'old',title:'Old',messages:[{role:'user',text:'long current answer'}]}];
 const backup={sessions:[{id:'old',title:'Old',messages:[{role:'user',text:'short'}]},{id:'lost',title:'Lost',busy:true,messages:[{role:'assistant',text:'restored',streaming:true}]}]};
 const result=mergeHistory(current,backup);assert.equal(result.length,3);assert.equal(result.find(s=>s.id==='old').messages[0].text,'long current answer');assert.equal(result.find(s=>s.id==='lost').busy,false);assert.equal(result.find(s=>s.id==='lost').messages[0].streaming,false);
 assert.equal(mergeHistory(result,backup).length,3);assert.throws(()=>mergeHistory(current,{sessions:[{id:'bad'}]}));assert.equal(current.length,2);
});
