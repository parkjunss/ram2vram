export function installDesktop({api,notify}) {
  const section=document.createElement('section');section.className='context-section';
  section.innerHTML=`<div class="section-title"><h2>화면 제어</h2></div><p id="desktop-status" role="status">상태 확인 중</p><button id="desktop-enable" class="secondary-button">화면 제어 허용</button><button id="desktop-stop" class="secondary-button">■ 화면 제어 긴급 중지</button><button id="desktop-open" class="secondary-button">창 목록 · 캡처</button><p class="muted">긴급 중지는 모든 에이전트의 화면 입력을 차단합니다. 다시 허용하기 전까지 유지됩니다.</p>`;
  document.querySelector('.activity-section').before(section);
  const dialog=document.createElement('dialog');dialog.id='desktop-dialog';
  dialog.innerHTML=`<div class="section-title"><h2>Windows 화면</h2><button id="desktop-close">닫기</button></div><p>창을 선택하고 캡처하거나 접근성 정보를 확인하세요. 캡처는 다른 창에 가려진 부분도 그대로 포함합니다.</p><button id="desktop-refresh">창 목록 새로고침</button><select id="desktop-window" aria-label="대상 창"></select><button id="desktop-capture">캡처</button><button id="desktop-inspect">접근성 정보</button><p id="desktop-error" role="alert"></p><img id="desktop-image" alt="선택한 창의 화면 캡처" hidden style="max-width:100%"><pre id="desktop-tree" style="white-space:pre-wrap;max-height:40vh;overflow:auto"></pre>`;
  document.body.append(dialog);const $=id=>document.getElementById(id);let windows=[];
  async function refresh(){try{const s=await api('/api/workspace/desktop');$('desktop-status').textContent=!s.supported?'Windows에서 사용할 수 있습니다':s.enabled?'허용됨 · 현재 대화의 승인 모드 적용':'중지됨';$('desktop-enable').disabled=!s.supported||s.enabled;$('desktop-stop').disabled=!s.supported;$('desktop-open').disabled=!s.supported||!s.enabled;}catch{$('desktop-status').textContent='서버 재시작 후 사용할 수 있습니다';}}
  async function set(enabled){try{await api('/api/workspace/desktop',{enabled});await refresh();}catch(e){notify(e.message);}}
  $('desktop-enable').onclick=()=>set(true);$('desktop-stop').onclick=()=>set(false);
  $('desktop-close').onclick=()=>{dialog.close();$('desktop-image').removeAttribute('src');$('desktop-image').hidden=true;$('desktop-tree').textContent='';};
  async function list(){try{const r=await api('/api/workspace/desktop/read',{action:'windows'});windows=r.windows;$('desktop-window').replaceChildren(...windows.map((w,i)=>new Option(`${w.title} (${w.pid})`,String(i))));$('desktop-error').textContent='';}catch(e){$('desktop-error').textContent=e.message;}}
  $('desktop-open').onclick=()=>{dialog.showModal();list();};$('desktop-refresh').onclick=list;
  async function read(action){const w=windows[Number($('desktop-window').value)];if(!w)return;try{$('desktop-error').textContent='조회 중…';const r=await api('/api/workspace/desktop/read',{action,windowId:w.windowId,pid:w.pid});if(r.image){$('desktop-image').src=`data:image/png;base64,${r.image}`;$('desktop-image').hidden=false;}else{$('desktop-tree').textContent=JSON.stringify(r,null,2);}$('desktop-error').textContent='';}catch(e){$('desktop-error').textContent=e.message;}}
  $('desktop-capture').onclick=()=>read('screenshot');$('desktop-inspect').onclick=()=>read('inspect');
  refresh();const timer=setInterval(refresh,5000);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
}
