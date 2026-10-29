export function mergeHistory(current, saved) {
  if (!saved || !Array.isArray(saved.sessions) || saved.sessions.length > 1000) throw new Error('올바른 채팅 백업 파일이 아닙니다.');
  const merged = new Map(current.map(s => [s.id, s]));
  for (const s of saved.sessions) {
    if (!s || typeof s.id !== 'string' || !s.id || typeof s.title !== 'string' || !Array.isArray(s.messages) || s.messages.some(m => !m || !['user','assistant'].includes(m.role) || typeof m.text !== 'string')) throw new Error('대화 데이터 형식이 올바르지 않습니다.');
    const old = merged.get(s.id);
    // Import is additive: never replace a newer or longer conversation.
    if (!old || JSON.stringify(s.messages).length > JSON.stringify(old.messages).length) merged.set(s.id, { ...s, busy:false, messages:s.messages.map(m=>({...m,streaming:false,tools:(m.tools||[]).map(t=>({...t,pendingDecision:false}))})) });
  }
  return [...merged.values()].sort((a,b)=>(b.created||0)-(a.created||0));
}
