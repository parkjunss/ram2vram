export const modes = Object.freeze({
  manual: { label:'◈ 승인 후 실행', permission:'manual', hint:'파일 변경과 명령 실행은 승인 요청을 확인한 뒤 진행합니다.' },
  plan: { label:'◇ 계획 · 읽기 전용', permission:'plan', hint:'파일과 자료를 읽어 계획을 작성합니다. 파일 변경과 쓰기 명령은 허용하지 않습니다.' },
  bypass: { label:'⚡ 자동 승인', permission:'bypass', hint:'파일 변경·명령 실행을 개별 승인 없이 수행합니다. 작업 폴더는 접근 제한 경계가 아닙니다.' },
  team: { label:'⇄ 자동 에이전트', permission:'bypass', hint:'자동 승인으로 실행하며 모델이 필요한 하위 에이전트를 생성·분담·취합합니다. 단일 GPU 슬롯에서는 순차 실행될 수 있습니다.' }
});
export const modeOf = value => Object.hasOwn(modes,value) ? value : 'manual';
export function turnRequest(message, selected) {
  const mode=modeOf(selected);
  // Commands must reach Harness unchanged (not become a model question).
  if(message.trim().startsWith('/'))return {mode:modes[mode].permission,message};
  const instruction = mode==='plan'
    ? '계획 모드: 필요한 파일과 자료를 읽고 목표, 구현 단계, 검증 방법을 한국어로 제시하세요. 파일을 수정하거나 구현을 실행하지 마세요.'
    : mode==='team'
      ? '자동 에이전트 모드: 먼저 작업을 분석하세요. 독립적으로 나눌 수 있는 작업은 실제 subagent 또는 subagent_fork 도구로 하위 에이전트를 생성해 맡기세요. 역할과 파일 책임을 겹치지 않게 정하고 필요한 만큼만 생성하세요. 결과를 기다리고 검증한 뒤 최종 답변을 취합하세요. 같은 파일을 여러 에이전트가 동시에 수정하지 않게 하세요. 단순한 요청은 직접 처리해도 됩니다. 생성하지 않은 에이전트를 생성했다고 말하지 마세요. 사용자에게는 한국어로 진행과 결과를 설명하세요.'
      : '';
  return {mode:modes[mode].permission,message:instruction ? `${instruction}\n\n사용자 요청:\n${message}` : message};
}
export function mergeAgent(agents, next) {
  if(!next || typeof next.id!=='string')return agents;
  const index=agents.findIndex(a=>a.id===next.id);
  if(index<0)agents.push({...next});else agents[index]={...agents[index],...next};
  return agents;
}
