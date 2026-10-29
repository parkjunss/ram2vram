export function formatBytes(value) { return `${(value / 1024 ** 3).toFixed(1)} GiB`; }

// NDJSON may split inside a UTF-8 character or leave its last frame without a newline.
export async function* readFrames(body) {
  if (!body) throw new Error('서버 응답 본문이 없습니다.');
  const reader = body.getReader(), decoder = new TextDecoder(); let buffer = '';
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split('\n'); buffer = lines.pop();
      for (const line of lines) if (line.trim()) yield JSON.parse(line);
      if (done) { if (buffer.trim()) yield JSON.parse(buffer); break; }
    }
  } finally { reader.releaseLock(); }
}

// Model and tool text are untrusted: build DOM nodes, never interpolate HTML.
export function renderText(container, text) {
  container.replaceChildren();
  const blocks = text.split(/```[^\n]*\n([\s\S]*?)```/g);
  blocks.forEach((block, index) => {
    if (index % 2) { const pre = document.createElement('pre'), code = document.createElement('code'); code.textContent = block; pre.append(code); container.append(pre); return; }
    const pattern = /\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>\])]+)|\*\*([^*\n]+)\*\*/g;
    let start = 0;
    for (const match of block.matchAll(pattern)) {
      container.append(document.createTextNode(block.slice(start, match.index)));
      if (match[4]) { const strong = document.createElement('strong'); strong.textContent = match[4]; container.append(strong); }
      else { const link = document.createElement('a'); link.textContent = match[1] || match[3]; link.href = match[2] || match[3]; link.target = '_blank'; link.rel = 'noopener noreferrer'; container.append(link); }
      start = match.index + match[0].length;
    } container.append(document.createTextNode(block.slice(start)));
  });
}
