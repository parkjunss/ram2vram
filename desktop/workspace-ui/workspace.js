import { readFrames, formatBytes, renderText } from './workspace-core.mjs';
import { mergeHistory } from './workspace-history.mjs';
import { modes, modeOf, turnRequest, mergeAgent } from './workspace-modes.mjs';
import { installDesktop } from './workspace-desktop.mjs';
import { installVision, installImageInput } from './workspace-vision.mjs';
import { installWorkspaceTools, compactText } from './workspace-tools.mjs?v=20261029-vision1';

const $ = id => document.getElementById(id);
const KEY = 'ram2vram.workspace.v1';
const createSession = () => ({ id: crypto.randomUUID(), title: '새 작업', created: Date.now(), messages: [], folder: null, busy: false });
let saved;
try { saved = JSON.parse(localStorage.getItem(KEY)); } catch { /* First run or invalid browser storage. */ }
const sessions = Array.isArray(saved?.sessions) ? saved.sessions.filter(s => typeof s.id === 'string' && Array.isArray(s.messages)) : [];
if (!sessions.length) sessions.push(createSession());
let active = sessions.find(s => s.id === saved?.active) || sessions[0];
let native = null, connected = false, selectedModel = '', workspace = null, controller = null, modelJob = null;
let saveTimer, pollBusy = false;
const reopened = new Set(sessions.filter(s => s.busy).map(s => s.id));

function banner(message = '') { $('banner').textContent = message; $('banner').hidden = !message; }
function persist(immediate = false) {
  clearTimeout(saveTimer);
  const flush = () => {
    try { localStorage.setItem(KEY, JSON.stringify({ active: active.id, sessions })); }
    catch { banner('대화 기록을 저장할 공간이 부족합니다. 이 창의 대화는 유지되지만 다시 열면 복구되지 않을 수 있습니다.'); }
  };
  if (immediate) flush(); else saveTimer = setTimeout(flush, 150);
}
async function api(path, data, method) {
  const response = await fetch(path, { method: method || (data === undefined ? 'GET' : 'POST'),
    headers: { 'Content-Type': 'application/json' }, body: data === undefined ? undefined : JSON.stringify(data) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `요청 실패 (${response.status})`);
  return result;
}
const node = (tag, className, text) => {
  const element = document.createElement(tag); if (className) element.className = className;
  if (text !== undefined) element.textContent = text; return element;
};
const busy = () => sessions.some(s => s.busy);
$('mode').replaceChildren(...Object.entries(modes).map(([key,value])=>new Option(value.label,key)));
const modeHint=node('p','mode-hint');modeHint.id='mode-hint';$('composer').after(modeHint);
$('mode').onchange=()=>{active.mode=modeOf($('mode').value);persist(true);controls();};
const historyActions = node('div', 'history-actions');
const exportHistory = node('button', 'text-button', '기록 내보내기');
const importHistory = node('button', 'text-button', '기록 가져오기');
const historyFile = node('input'); historyFile.type = 'file'; historyFile.accept = '.json,application/json'; historyFile.hidden = true; historyFile.id='history-file';
historyActions.append(exportHistory, importHistory, historyFile); $('sessions').after(historyActions);
exportHistory.onclick = () => {
  const url=URL.createObjectURL(new Blob([JSON.stringify({active:active.id,sessions},null,2)],{type:'application/json'}));
  const a=node('a');a.href=url;a.download='ram2vram-chats.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
importHistory.onclick = () => { if(busy()){banner('진행 중인 응답을 마친 뒤 기록을 가져오세요.');return;}historyFile.click(); };
historyFile.onchange = async () => {
  const file=historyFile.files[0];if(!file)return;
  try {
    if(busy())throw new Error('진행 중인 응답을 마친 뒤 가져오세요.');
    if(file.size>64*1024*1024)throw new Error('64MiB 이하의 채팅 백업 파일을 선택하세요.');
    const imported=JSON.parse(await file.text());const merged=mergeHistory(sessions,imported);
    const next=merged.find(s=>s.id===imported.active&&s.messages.length)||merged.find(s=>s.messages.length)||merged[0];
    // Save successfully before replacing the visible state.
    localStorage.setItem(KEY,JSON.stringify({active:next.id,sessions:merged}));
    sessions.splice(0,sessions.length,...merged);active=next;render();banner(`기록을 가져왔습니다. 대화 ${sessions.filter(s=>s.messages.length).length}개가 보관되어 있습니다.`);
  }catch(e){banner('기록 가져오기 실패: '+e.message);}finally{historyFile.value='';}
};
const responseDefaults = { temperature: 0.6, top_p: 0.95, top_k: 40, max_tokens: 4096, korean: true, logit_bias: {} };
const settingsButton = node('button', 'secondary-button', '모델 응답 설정');
settingsButton.id = 'generation-settings'; $('load-model').after(settingsButton);
function showSettings(value) {
  for (const key of ['temperature','top_p','top_k','max_tokens']) $('setting-' + key).value = value[key];
  $('setting-korean').checked = value.korean;
  $('setting-logit_bias').value = JSON.stringify(value.logit_bias, null, 2);
}
settingsButton.onclick = async () => {
  try { showSettings(await api('/api/workspace/generation')); $('settings-error').textContent = ''; $('settings-dialog').showModal(); }
  catch (e) { banner(e.message); }
};
$('settings-close').onclick = () => $('settings-dialog').close();
$('settings-reset').onclick = () => showSettings(responseDefaults);
$('settings-form').onsubmit = async e => {
  e.preventDefault();
  if (busy()) { $('settings-error').textContent = '응답을 마치거나 중지한 뒤 저장하세요.'; return; }
  try {
    const value = { korean: $('setting-korean').checked, logit_bias: JSON.parse($('setting-logit_bias').value || '{}') };
    for (const key of ['temperature','top_p','top_k','max_tokens']) value[key] = Number($('setting-' + key).value);
    await api('/api/workspace/generation', value); $('settings-dialog').close(); banner('모델 응답 설정을 저장했습니다. 이후 로컬 에이전트 요청에 적용됩니다.');
  } catch (e) { $('settings-error').textContent = e.message; }
};
const ready = () => native?.instances?.find(i => i.status === 'ready' && (!selectedModel || i.model === selectedModel));
const toolsOf = s => s.messages.flatMap(m => m.tools || []);
const visionTools=installVision({api,notify:banner,state:()=>({native,model:selectedModel,ready:ready(),busy:busy(),job:modelJob}),onJob:id=>{modelJob=id;controls();poll();}});
const imageInput=installImageInput({notify:banner,state:()=>({session:active.id,ready:ready(),busy:busy()})});
installDesktop({api,notify:banner});
const workspaceTools = installWorkspaceTools({
  api, notify: banner,
  state: () => ({ session: active, model: selectedModel, modelJob, connected, ready: ready(), busy: busy() }),
  onJob: id => { modelJob = id; controls(); poll(); },
  compact: () => {
    if (busy() || !ready()) return;
    const draft = $('prompt').value; $('prompt').value = '/compact';
    $('composer').requestSubmit(); $('prompt').value = draft; controls();
  }
});
const toolNames = { read: '파일 읽기', write: '파일 쓰기', edit: '파일 수정', glob: '파일 찾기', grep: '내용 검색', pwsh: '명령 실행', bash: '명령 실행', web_search: '웹 검색', web_fetch: '페이지 읽기' };
const toolStates = { running: '실행 중', proposed: '승인 필요', done: '완료', denied: '거부됨', error: '실패' };

function controls() {
  const currentMode=modeOf(active.mode);$('mode').value=currentMode;modeHint.textContent=modes[currentMode].hint;modeHint.dataset.automatic=String(modes[currentMode].permission==='bypass');
  workspaceTools.update();
  visionTools.update();imageInput.update();
  settingsButton.disabled = busy() || !connected;
  $('new-chat').disabled = busy(); $('send').disabled = active.busy || !connected || !ready() || !$('prompt').value.trim();
  $('stop').hidden = !active.busy; $('send').hidden = active.busy;
  $('choose-folder').disabled = active.busy; $('mode').disabled = active.busy; $('model-select').disabled = busy() || !!modelJob;
  $('load-model').disabled = busy() || !!modelJob || !connected || !selectedModel || !!ready();
  $('load-model').textContent = ready() ? '사용 중' : modelJob ? '모델 로딩 중…' : '모델 로드';
  $('composer-model').textContent = ready()?.label || (connected ? '모델을 먼저 로드하세요' : '서버 연결 끊김');
  $('run-status').textContent = reopened.has(active.id) ? '이전 응답 연결이 끊겼습니다. 중지 버튼으로 서버 작업을 정리한 뒤 계속하세요.' : active.busy ? '모델이 작업하고 있습니다. 도구 요청을 확인하세요.' : ready() ? '준비됐습니다. 어떤 작업부터 시작할까요?' : '오른쪽에서 모델을 로드하면 대화를 시작할 수 있습니다.';
}
function renderSessions() {
  $('sessions').replaceChildren(); $('session-count').textContent = sessions.length;
  for (const s of sessions) {
    const button = node('button', 'session-button' + (s.id === active.id ? ' active' : ''), s.title);
    button.append(node('small', '', new Date(s.created).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })));
    button.disabled = busy() && s.id !== active.id;
    button.onclick = () => { active = s; render(); refreshFolder(); persist(); };
    $('sessions').append(button);
  }
  $('chat-title').textContent = active.title;
}
function renderFolder() {
  const path = active.folder || workspace?.path || '';
  $('folder-path').textContent = path || '서버에 연결하면 작업 폴더가 표시됩니다.';
  $('folder-name').textContent = path.split(/[\\/]/).filter(Boolean).pop() || '작업 폴더';
}
async function refreshFolder() {
  const session = active;
  try { const result = await api('/api/chat/folder?sessionId=' + encodeURIComponent(session.id)); session.folder = result.folder?.path || result.folder || null; if (typeof session.folder !== 'string') session.folder = null; renderFolder(); persist(); }
  catch (e) { banner(e.message); }
}
function toolCard(tool, sessionId) {
  const card = node('div', 'tool-card ' + tool.state);
  const heading = node('div', 'tool-header'); heading.append(node('strong', '', toolNames[tool.name] || tool.name), node('span', 'tool-state', toolStates[tool.state] || tool.state)); card.append(heading);
  card.append(node('span', 'tool-target', tool.preview || tool.target || ''));
  if (tool.state === 'proposed') {
    card.append(node('p', '', tool.effect || '이 작업을 실행할까요?'));
    const detail = node('details'); detail.append(node('summary', '', '요청 내용 확인'), node('pre', '', JSON.stringify(tool.args || {}, null, 2))); card.append(detail);
    const actions = node('div', 'tool-actions');
    for (const [decision, label] of [['approve', '이번 작업 승인'], ['deny', '거부']]) {
      const button = node('button', decision, label); button.disabled = !!tool.pendingDecision;
      button.onclick = async () => {
        tool.pendingDecision = true; renderMessages();
        try { await api('/api/chat/approval', { sessionId, toolId: tool.id, decision }); if (tool.state === 'proposed') tool.state = decision === 'approve' ? 'running' : 'denied'; }
        catch (e) { banner(e.message); }
        finally { tool.pendingDecision = false; persist(); renderMessages(); }
      }; actions.append(button);
    } card.append(actions);
  } else if (tool.result) {
    const detail = node('details'); detail.append(node('summary', '', '실행 결과'), node('pre', '', String(tool.result))); card.append(detail);
  }
  return card;
}
function renderMessages() {
  const viewport = $('conversation'); const bottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 120;
  $('welcome').hidden = active.messages.length > 0; $('messages').replaceChildren();
  for (const message of active.messages) {
    const card = node('article', 'message ' + message.role);
    const label = node('div', 'message-label');
    if (message.role !== 'user') label.append(node('span', 'avatar', 'R'));
    label.append(node('span', '', message.role === 'user' ? 'YOU' : 'RAM2VRAM'));
    if (message.streaming) label.append(node('span', 'pending-pulse')); card.append(label);
    const text = node('div', 'message-text'); renderText(text, message.text || ''); card.append(text);
    for (const tool of message.tools || []) card.append(toolCard(tool, active.id));
    if(message.mode && message.role==='user')card.append(node('small','turn-mode',modes[modeOf(message.mode)].label));
    if(message.imageNames?.length)card.append(node('p','muted','첨부 이미지: '+message.imageNames.join(', ')));
    const agentLabels={queued:'대기 중',working:'실행 중',completed:'완료',failed:'실패',cancelled:'중지됨'};
    for(const agent of message.agents||[]){
      const row=node('div','agent-card');row.append(node('strong','',agent.name||'하위 에이전트'),node('span','agent-state',agentLabels[agent.status]||agent.status||'상태 확인 중'));
      row.append(node('p','',agent.description||''));card.append(row);
    }
    if (message.skills?.length) card.append(node('p', 'used-skills', '사용한 스킬: ' + message.skills.map(s => s.name).join(', ')));
    if (message.error) card.append(node('p', 'message-error', message.error));
    $('messages').append(card);
  }
  const tools = toolsOf(active); $('tool-count').textContent = tools.length; $('activity').replaceChildren();
  if (!tools.length) $('activity').append(node('p', 'empty-activity', '도구를 사용하면 여기에\n실행 과정이 표시됩니다.'));
  for (const tool of tools.slice(-8).reverse()) { const row = node('div', 'activity-item'); row.append(node('strong', '', (toolNames[tool.name] || tool.name) + ' · ' + (toolStates[tool.state] || tool.state)), node('small', '', tool.target || tool.preview || '')); $('activity').append(row); }
  if (bottom) viewport.scrollTop = viewport.scrollHeight;
}
function render() { renderSessions(); renderFolder(); renderMessages(); controls(); }
function meter(prefix, used, total) {
  const valid = Number.isFinite(used) && Number.isFinite(total) && total > 0;
  $(prefix + '-value').textContent = valid ? `${formatBytes(used)} / ${formatBytes(total)}` : '측정값 없음';
  $(prefix + '-bar').style.width = valid ? `${Math.max(0, Math.min(100, used / total * 100))}%` : '0';
}
async function poll() {
  if (pollBusy) return; pollBusy = true;
  try {
    native = await api('/api/native'); connected = true;
    const models = (native.installed?.models || []).filter(m => m.ready);
    if (!selectedModel) selectedModel = native.instances?.find(i => i.status === 'ready')?.model || models.find(m => m.model.toLowerCase() === 'iq2_xs')?.model || models[0]?.model || '';
    const select = $('model-select');
    if (select.dataset.models !== JSON.stringify(models.map(m => m.model))) {
      select.replaceChildren(...models.map(m => new Option(m.model_name || m.model, m.model)));
      if (!models.length) select.add(new Option('설치된 모델이 없습니다', ''));
      select.dataset.models = JSON.stringify(models.map(m => m.model));
    } select.value = selectedModel;
    if (modelJob) { const job = native.jobs?.find(j => j.id === modelJob); if (job?.state === 'error') { banner(job.error || '모델 로딩 실패'); modelJob = null; } else if (job?.state === 'done') modelJob = null; }
    const instance = ready(); const metrics = instance?.metrics; const hw = metrics?.hardware || {};
    meter('ram', hw.ram_used, hw.ram_total); meter('vram', hw.gpu_mem_used, hw.gpu_mem_total);
    const cache = metrics?.engine?.expert_cache_mib;
    $('cache-value').textContent = Number.isFinite(cache) ? `${(cache / 1024).toFixed(1)} GiB` : '—';
    const speed = metrics?.live?.state === 'generating' ? metrics.live.tok_s : metrics?.requests?.[0]?.decode_tok_s;
    $('speed-value').textContent = Number.isFinite(speed) ? speed.toFixed(1) : '—';
    $('connection-text').textContent = instance ? '로컬 모델 연결됨' : '서버 연결됨'; $('connection-dot').className = 'dot green';
    $('model-badge').textContent = instance ? 'READY' : modelJob ? 'LOADING' : 'IDLE';
    if (!workspace) { const result = await api('/api/workspaces'); workspace = (Array.isArray(result) ? result : result.workspaces)?.[0]; renderFolder(); }
  } catch { connected = false; native = null; meter('ram'); meter('vram'); $('cache-value').textContent = '—'; $('speed-value').textContent = '—'; $('connection-text').textContent = '서버 연결 끊김'; $('connection-dot').className = 'dot'; $('model-badge').textContent = 'OFFLINE'; }
  finally { pollBusy = false; controls(); }
}

$('new-chat').onclick = () => { if (busy()) return; active = createSession(); sessions.unshift(active); render(); persist(); $('prompt').focus(); };
$('prompt').oninput = controls;
$('prompt').onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!$('send').disabled) $('composer').requestSubmit(); } };
document.addEventListener('keydown', e => { if (e.ctrlKey && e.key.toLowerCase() === 'n' && !e.altKey) { e.preventDefault(); if (!busy()) $('new-chat').click(); } });
document.querySelectorAll('[data-prompt]').forEach(button => button.onclick = () => { $('prompt').value = button.dataset.prompt; $('prompt').focus(); controls(); });
$('model-select').onchange = () => { selectedModel = $('model-select').value; controls(); };
$('load-model').onclick = async () => { try { banner(); const result = await api('/api/native/operations', { kind: 'load', args: { model: selectedModel, values: { parallel: 1 } } }); modelJob = result.id; controls(); } catch (e) { banner(e.message); } };
$('choose-folder').onclick = () => { $('folder-input').value = active.folder || workspace?.path || ''; $('folder-error').textContent = ''; $('folder-dialog').showModal(); $('folder-input').focus(); };
$('cancel-folder').onclick = () => $('folder-dialog').close();
$('folder-form').onsubmit = async e => { e.preventDefault(); try { const result = await api('/api/chat/folder', { sessionId: active.id, path: $('folder-input').value.trim() }); active.folder = result.folder?.path || result.folder || $('folder-input').value.trim(); $('folder-dialog').close(); renderFolder(); persist(); } catch (error) { $('folder-error').textContent = error.message; } };
$('composer').onsubmit = async e => {
  e.preventDefault(); const prompt = $('prompt').value.trim(); const model = ready(); if (!prompt || busy() || !model) return;
  let images;try{images=imageInput.take();}catch(error){banner(error.message);return;}
  const session = active; banner(); session.busy = true;
  if (!session.messages.length) session.title = prompt.slice(0, 36);
  const selectedMode=modeOf(session.mode), request=turnRequest(prompt,selectedMode);
  session.messages.push({ role: 'user', text: prompt, mode:selectedMode, imageNames:images.map(i=>i.name) }); const answer = { role: 'assistant', text: '', tools: [], agents:[], streaming: true }; session.messages.push(answer);
  $('prompt').value = ''; persist(); render(); $('conversation').scrollTop = $('conversation').scrollHeight; controller = new AbortController(); let done = false;
  try {
    const response = await fetch('/api/chat/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
      body: JSON.stringify({ sessionId: session.id, workspaceId: workspace?.id || 'root', nativeModelId: model.id, ...request, images, thinking: 'off' }) });
    if (!response.ok) throw new Error((await response.json()).error || `요청 실패 (${response.status})`);
    for await (const frame of readFrames(response.body)) {
      if (frame.type === 'delta') answer.text += compactText(frame);
      if (frame.type === 'agent-tool') { const previous = answer.tools.find(t => t.id === frame.tool.id); if (previous) Object.assign(previous, frame.tool); else answer.tools.push(frame.tool); }
      if (frame.type === 'skills-used' && Array.isArray(frame.skills)) answer.skills = frame.skills.filter(s => s && typeof s.name === 'string');
      if (frame.type === 'agent') mergeAgent(answer.agents,frame.agent);
      if (frame.type === 'error') answer.error = frame.message || frame.error || '모델 요청이 실패했습니다.';
      if (frame.type === 'notice') banner(frame.message || frame.text || '도구 실행 상태를 확인하세요.');
      if (frame.type === 'status' && frame.phase === 'compacting') banner('컨텍스트 여유를 확보하기 위해 이전 대화를 압축하고 있습니다.');
      if (frame.type === 'done') { done = true; if ($('banner').textContent === '컨텍스트 여유를 확보하기 위해 이전 대화를 압축하고 있습니다.') banner(); if (frame.cancelled) answer.error = '작업이 중지됐습니다.'; }
      persist(); if (active.id === session.id) renderMessages();
    }
    if (!done) throw new Error('응답 연결이 끊겼습니다. 서버 작업을 중지한 뒤 계속하세요.');
  } catch (error) {
    if (error.name !== 'AbortError') { answer.error = error.message; reopened.add(session.id); }
    else answer.error = '작업이 중지됐습니다.';
  } finally {
    answer.streaming = false; session.busy = reopened.has(session.id); controller = null; persist(true); render(); poll(); workspaceTools.refreshContext();
  }
};
$('stop').onclick = async () => {
  $('stop').disabled = true;
  try { await api('/api/chat/stop', { sessionId: active.id }); reopened.delete(active.id); active.busy = false; controller?.abort(); for (const m of active.messages) m.streaming = false; persist(); render(); }
  catch (e) { banner(e.message); }
  finally { $('stop').disabled = false; }
};
window.addEventListener('pagehide', () => persist(true));
window.addEventListener('beforeunload', e => { persist(true); if (busy()) { e.preventDefault(); e.returnValue = ''; } });
render(); poll(); refreshFolder(); setInterval(poll, 4000);
