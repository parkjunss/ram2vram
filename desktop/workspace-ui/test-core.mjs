import test from 'node:test';
import assert from 'node:assert/strict';
import { readFrames } from './workspace-core.mjs';

test('stream preserves split Korean UTF-8, multiple frames, and final unterminated frame', async () => {
  const bytes = new TextEncoder().encode('{"type":"delta","text":"안녕"}\n\n{"type":"done"}');
  const body = new ReadableStream({ start(controller) { for (let n=0;n<bytes.length;n+=2) controller.enqueue(bytes.slice(n,n+2)); controller.close(); } });
  const frames = []; for await (const frame of readFrames(body)) frames.push(frame);
  assert.deepEqual(frames, [{type:'delta',text:'안녕'},{type:'done'}]);
});
test('invalid server frames fail rather than silently showing a successful answer', async () => {
  const body = new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode('{bad}\n')); c.close(); } });
  await assert.rejects(async () => { for await (const frame of readFrames(body)) void frame; });
});
