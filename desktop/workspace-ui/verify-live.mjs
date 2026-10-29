// Explicit opt-in: uses the running local model and synthetic files only.
import { chromium } from '../strata/apps/host/node_modules/playwright-core/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import assert from 'node:assert/strict';

const output = resolve('.ram2vram-desktop/logs/workspace-ui');
await mkdir(output, { recursive: true });
const fixture = resolve(output, 'live-input.txt');
const nonce = 'WORKSPACE_OK_' + randomUUID();
await writeFile(fixture, nonce, 'utf8');
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 920 } });
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:47832/workspace/index.html');
  await page.waitForFunction(() => document.querySelector('#connection-text').textContent.includes('연결됨'));
  await page.locator('#generation-settings').click();
  await page.locator('#settings-reset').click();
  await page.locator('#settings-form button[type=submit]').click();
  await page.waitForFunction(() => !document.querySelector('#settings-dialog').open);
  if (await page.locator('#load-model').isEnabled()) await page.locator('#load-model').click();
  await page.waitForFunction(() => document.querySelector('#connection-text').textContent === '로컬 모델 연결됨', {}, { timeout: 300000 });
  await page.locator('#prompt').fill(`Use the read tool to read ${fixture.replaceAll('\\', '/')}. Reply with the exact content. Do not use any other tools or delegate.`);
  await page.locator('#send').click();
  await page.waitForFunction(() => document.querySelector('.tool-card.done'), { }, { timeout: 180000 });
  await page.waitForFunction(() => document.querySelector('#stop').hidden, {}, { timeout: 180000 });
  assert.match(await page.locator('.message.assistant .message-text').innerText(), new RegExp(nonce));
  await page.screenshot({ path: resolve(output, 'live-read.png'), fullPage: true });
  await page.reload();
  await page.waitForFunction(value => document.querySelector('#messages').textContent.includes(value), nonce);
  assert.deepEqual(errors, []);
  console.log('PASS: actual Qwen stream, file tool, exact nonce, persisted reply, real metrics screenshot');
} finally { await browser.close(); }
