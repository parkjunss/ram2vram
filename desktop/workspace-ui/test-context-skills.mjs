import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync,readFileSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {contextTokens,withContext,compactionInfo} from '../strata/apps/host/server/workspace-context.mjs';
import {parseImportedSkill} from './workspace-tools.mjs';
import {writeCreatedSkill,materializeSkills} from '../strata/apps/host/server/skill-files.mjs';

test('context replaces all forms, preserves cache flags and rejects invalid windows',()=>{
 const args=['--pcie-frac','1','--max-context=65536','--expert-cache','auto','--max-context','32768'];
 const next=withContext(args,24576);assert.equal(contextTokens(next),24576);assert.deepEqual(next,['--pcie-frac','1','--expert-cache','auto','--max-context','24576']);
 assert.equal(contextTokens(args),32768);
 for(const n of [0,16383,16385,Infinity,131073,'32768'])assert.throws(()=>withContext(args,n));
 assert.ok(compactionInfo(32768).triggerTokens<32768-4096);
});
test('Korean skill names persist, disabled skills are hidden, imported content is preserved',()=>{
 const root=mkdtempSync(join(tmpdir(),'ram2vram-skills-'));
 try {
  const id=writeCreatedSkill(root,{name:'문서 정리',description:'문서를 요약할 때 사용',body:'경로와 출처를 보존한다.'});
  const file=join(root,id,'SKILL.md');assert.ok(existsSync(file));
  const parsed=parseImportedSkill(readFileSync(file,'utf8'));assert.equal(parsed.name,'문서 정리');assert.equal(parsed.body,'경로와 출처를 보존한다.');
  materializeSkills(join(root,'live'),[{id,name:parsed.name,description:parsed.description,body:parsed.body,enabled:false}]);
  assert.match(readFileSync(join(root,'live',id,'SKILL.md'),'utf8'),/disable-model-invocation: true/);
  assert.throws(()=>parseImportedSkill(''));
 }finally{assert.ok(resolve(root).startsWith(resolve(tmpdir())));rmSync(root,{recursive:true,force:true});}
});
