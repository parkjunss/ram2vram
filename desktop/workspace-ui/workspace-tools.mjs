const $ = id => document.getElementById(id);
const element = (tag, text, className) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; };

export function installWorkspaceTools({ api, state, notify, onJob, compact }) {
  const section = element('section', undefined, 'context-section');
  section.innerHTML = `<div class="section-title"><h2>컨텍스트 · 스킬</h2></div>
    <p id="context-usage">사용량 확인 전</p><div class="meter-track"><i id="context-bar"></i></div>
    <p id="context-policy" class="muted">자동 압축 켜짐 · 오래된 대화를 요약합니다.</p>
    <button id="context-settings" class="secondary-button">컨텍스트 한도 설정</button>
    <button id="compact-now" class="secondary-button">지금 대화 압축</button>
    <button id="skills-open" class="secondary-button">스킬 관리</button>`;
  document.querySelector('.activity-section').before(section);
  const dialogs = element('div');
  dialogs.innerHTML = `<dialog id="context-dialog"><form id="context-form">
    <div class="section-title"><h2>컨텍스트 한도</h2><button type="button" id="context-close">닫기</button></div>
    <p id="context-current"></p><label for="context-limit">입력·대화·도구 결과·출력이 공유하는 토큰 한도</label>
    <input id="context-limit" type="number" min="16384" max="131072" step="1024" required>
    <p>16K~128K, 1024 단위입니다. 큰 한도는 RAM·VRAM 사용량을 늘리고 expert 캐시를 줄일 수 있습니다. 저장만 하면 다음 모델 로드부터 적용됩니다.</p>
    <p>자동 압축은 출력 여유를 확보하도록 엔진의 대화 관리 계층이 수행합니다. 화면의 원본 대화 기록은 지우지 않습니다. 요약에는 일부 세부 내용이 빠질 수 있습니다.</p>
    <button type="submit" class="secondary-button" value="save">저장만</button>
    <button type="submit" class="primary-button" value="reload">저장 후 모델 재로드</button>
    <p id="context-error" role="alert"></p></form></dialog>
    <dialog id="skills-dialog"><div class="section-title"><h2>스킬 관리</h2><button id="skills-close">닫기</button></div>
    <p>스킬은 모델이 필요할 때 읽는 작업 지침입니다. 활성화해도 모든 답변에서 실행되는 것은 아니며 도구 권한을 추가하지 않습니다. 변경은 다음 요청부터 적용됩니다.</p>
    <div class="skill-actions"><button id="skill-new">새 스킬</button><label class="file-button">SKILL.md 불러오기<input id="skill-file" type="file" accept=".md,text/markdown,text/plain"></label></div>
    <p>불러오기는 지침 파일만 지원합니다. 연결된 스크립트·폴더는 가져오지 않습니다.</p>
    <p id="skills-error" role="alert"></p><div id="skills-list"></div>
    <form id="skill-form" hidden><h3 id="skill-editor-title">새 스킬</h3>
      <label>이름<input id="skill-name" maxlength="80" required></label>
      <label>사용할 때 / 설명<input id="skill-description" maxlength="400" required></label>
      <label>작업 지침<textarea id="skill-body" rows="9" maxlength="40000" required></textarea></label>
      <label><input id="skill-enabled" type="checkbox" checked> 활성화</label>
      <button type="submit" class="primary-button">저장</button> <button id="skill-cancel" type="button">취소</button>
    </form></dialog>`;
  document.body.append(dialogs);
  let context = null, skills = [], editing = null, pending = false, refreshPending = false, identity = '';
  const message = e => { $('skills-error').textContent = e.message || String(e); };
  function update() {
    const s = state();
    $('context-settings').disabled = s.busy || !s.connected || !s.model || !!s.modelJob;
    $('compact-now').disabled = s.busy || !s.ready || !s.session.messages.length;
    $('skills-open').disabled = s.busy || !s.connected;
    const key = `${s.session.id}/${s.ready?.id || ''}/${s.model}`;
    if (key !== identity) { identity = key; context = null; drawContext(); void refreshContext(); }
  }
  function drawContext() {
    const window = context?.appliedTokens;
    const tokens = context?.context && context.context.window === window ? context.context.tokens : null;
    $('context-usage').textContent = Number.isFinite(tokens) && window > 0 ? `${tokens.toLocaleString()} / ${window.toLocaleString()} 토큰` : window > 0 ? `적용 한도 ${window.toLocaleString()} 토큰 · 대화 측정 전` : '모델 로드 후 확인할 수 있습니다.';
    $('context-bar').style.width = Number.isFinite(tokens) && window > 0 ? `${Math.min(100, tokens/window*100)}%` : '0';
    const trigger = context?.autoCompact?.triggerTokens;
    $('context-policy').textContent = trigger ? `자동 압축 켜짐 · 약 ${trigger.toLocaleString()} 토큰에서 요약 검토` : '자동 압축 켜짐 · 출력 여유에 따라 오래된 대화를 요약합니다.';
  }
  async function refreshContext() {
    const s = state(); if (!s.connected || !s.model || refreshPending) return;
    const key = `${s.session.id}/${s.ready?.id || ''}/${s.model}`; refreshPending = true;
    try {
      const result = await api(`/api/workspace/context?model=${encodeURIComponent(s.model)}&sessionId=${encodeURIComponent(s.session.id)}`);
      if (key === identity) { context = result; drawContext(); }
    } catch (e) { if ($('context-dialog').open) $('context-error').textContent = e.message; }
    finally { refreshPending = false; }
  }
  $('context-settings').onclick = async () => {
    $('context-error').textContent = ''; $('context-dialog').showModal();
    $('context-limit').disabled = true;
    await refreshContext();
    $('context-limit').value = context?.savedTokens || context?.appliedTokens || 32768;
    $('context-current').textContent = `저장값: ${context?.savedTokens ?? '없음'} · 현재 적용값: ${context?.appliedTokens ?? '모델 미로드'}`;
    $('context-limit').disabled = false;
  };
  $('context-close').onclick = () => $('context-dialog').close();
  $('context-form').onsubmit = async e => {
    e.preventDefault(); if (pending || state().busy) return;
    pending = true; const buttons = [...$('context-form').querySelectorAll('button[type=submit]')]; buttons.forEach(b => b.disabled = true);
    try {
      const model=state().model, reload=e.submitter?.value === 'reload';
      await api('/api/workspace/context', { model, tokens: Number($('context-limit').value), reload:false });
      // Load through the native operation so even an already-running older host preserves the saved vision choice.
      if (reload) {const job=await api('/api/native/operations',{kind:'load',args:{model,values:{parallel:1}}});onJob(job.id);}
      $('context-dialog').close(); notify(reload ? '컨텍스트를 저장하고 모델을 재로드합니다.' : '컨텍스트 한도를 저장했습니다. 다음 모델 로드부터 적용됩니다.');
      await refreshContext();
    } catch (e) { $('context-error').textContent = e.message; }
    finally { pending = false; buttons.forEach(b => b.disabled = false); }
  };
  $('compact-now').onclick = () => { if (!state().busy) compact(); };
  async function refreshSkills() { skills = await api('/api/skills'); drawSkills(); }
  function editor(skill = null) {
    editing = skill?.id || null; $('skill-editor-title').textContent = editing ? '스킬 편집' : '새 스킬';
    $('skill-name').value = skill?.name || ''; $('skill-description').value = skill?.description || ''; $('skill-body').value = skill?.body || ''; $('skill-enabled').checked = skill?.enabled !== false;
    $('skill-form').hidden = false; $('skill-name').focus(); $('skill-form').scrollIntoView({block:'nearest'});
  }
  function drawSkills() {
    $('skills-list').replaceChildren();
    for (const skill of skills) {
      const row = element('div', undefined, 'skill-row'); const heading = element('div', undefined, 'section-title');
      heading.append(element('strong', skill.name), element('span', skill.source === 'created' ? '내 스킬' : skill.source === 'bundled' ? '기본' : '가져옴', 'muted'));
      row.append(heading, element('p', skill.description));
      const actions = element('div', undefined, 'skill-actions');
      const toggle = element('button', skill.enabled ? '활성 · 끄기' : '비활성 · 켜기');
      toggle.onclick = async () => { if (pending) return; pending = true; toggle.disabled = true; try { await api('/api/skills/'+encodeURIComponent(skill.id), {enabled:!skill.enabled}, 'PATCH'); await refreshSkills(); } catch(e) {message(e);} finally {pending=false;toggle.disabled=false;} };
      const edit = element('button', '편집'); edit.onclick = () => editor(skill);
      const exportButton = element('button', '내보내기'); exportButton.onclick = () => {
        const text = `---\nname: ${JSON.stringify(skill.id)}\ntitle: ${JSON.stringify(skill.name)}\ndescription: ${JSON.stringify(skill.description)}\n---\n\n${skill.body}\n`;
        const url = URL.createObjectURL(new Blob([text], {type:'text/markdown;charset=utf-8'})); const link=element('a'); link.href=url;link.download='SKILL.md';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      };
      actions.append(toggle, edit, exportButton);
      if (skill.source === 'created') {
        const remove = element('button', '삭제'); let confirm = false;
        remove.onclick = async () => { if (!confirm) {confirm=true;remove.textContent='정말 삭제';return;} if(pending)return;pending=true;try {await api('/api/skills/'+encodeURIComponent(skill.id), undefined, 'DELETE'); if(editing===skill.id)$('skill-form').hidden=true;await refreshSkills();}catch(e){message(e);}finally{pending=false;} };
        actions.append(remove);
      }
      row.append(actions); $('skills-list').append(row);
    }
  }
  $('skills-open').onclick = async () => { $('skills-error').textContent='';$('skill-form').hidden=true;$('skills-dialog').showModal();try {await refreshSkills();}catch(e){message(e);} };
  $('skills-close').onclick = () => $('skills-dialog').close();
  $('skill-new').onclick = () => editor(); $('skill-cancel').onclick = () => $('skill-form').hidden = true;
  $('skill-form').onsubmit = async e => {
    e.preventDefault(); if(pending)return;pending=true;
    const submit=$('skill-form').querySelector('button[type=submit]');submit.disabled=true;
    try {
      const data={name:$('skill-name').value.trim(),description:$('skill-description').value.trim(),body:$('skill-body').value.trim(),enabled:$('skill-enabled').checked};
      await api(editing ? '/api/skills/'+encodeURIComponent(editing) : '/api/skills', data, editing?'PATCH':'POST');
      $('skill-form').hidden=true;await refreshSkills();$('skills-error').textContent='';
    } catch(e) {message(e);} finally {pending=false;submit.disabled=false;}
  };
  $('skill-file').onchange = async () => {
    const file=$('skill-file').files[0];if(!file)return;
    try {if(file.size>65536)throw new Error('64KiB 이하의 SKILL.md 파일을 선택하세요.');const skill=parseImportedSkill(await file.text());editor(skill);}catch(e){message(e);}finally{$('skill-file').value='';}
  };
  return { update, refreshContext };
}

export function parseImportedSkill(text) {
  const raw = text.replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');
  const front = /^---\n([\s\S]*?)\n---\n?/.exec(raw);
  const read = key => { const value = new RegExp(`^${key}:\\s*(.+)$`,'m').exec(front?.[1] || '')?.[1]?.trim(); if(!value)return '';try{return String(JSON.parse(value));}catch{return value.replace(/^'|'$/g,'');} };
  const body = (front ? raw.slice(front[0].length) : raw).trim();
  if(!body || body.length>40000)throw new Error('작업 지침은 1~40000자여야 합니다.');
  return {name:(read('title') || read('name')).slice(0,80),description:read('description').slice(0,400),body,enabled:true};
}

const compactMessages = new Map([
  ['Older messages were summarized to make room. The chat was {0}% full and is now {1}% full.', '이전 대화를 요약했습니다. 컨텍스트 사용률: {0}% → {1}%.'],
  ['Older messages were summarized to make room. The chat was {0}% full.', '이전 대화를 요약했습니다. 압축 전 컨텍스트 사용률: {0}%.'],
  ['Older messages were summarized to make room.', '컨텍스트 여유를 확보하기 위해 이전 대화를 요약했습니다.'],
  ['There is nothing older to summarize yet. Everything in this chat is still needed by the assistant.', '아직 요약할 오래된 대화가 없습니다. 현재 내용은 작업에 필요한 상태입니다.'],
  ['There is nothing to summarize yet. This chat has not started a conversation with the assistant.', '아직 모델과 대화를 시작하지 않아 요약할 내용이 없습니다.'],
  ['The older messages could not be summarized right now. Try again in a moment, or start a new chat.', '대화를 압축하지 못했습니다. 잠시 후 다시 시도하거나 새 대화를 시작하세요.'],
  ['This chat is still working. Stop it or wait for it to finish, then try again.', '대화가 진행 중입니다. 완료하거나 중지한 뒤 다시 압축하세요.'],
  ['This chat is {0}% full, but there is nothing older to summarize: the newest message is what fills it. Start a new chat, or send a shorter message.', '컨텍스트 사용률은 {0}%이며 최신 메시지가 대부분을 차지합니다. 새 대화를 시작하거나 메시지를 줄여 주세요.']
]);
export function compactText(frame) {
  const text = compactMessages.get(frame.key);
  return text ? (frame.noteReason === 'compacted' ? '\n\n' : '') + text.replace(/\{(\d+)\}/g, (_, i) => String(frame.values?.[Number(i)] ?? '')) : frame.text || '';
}
