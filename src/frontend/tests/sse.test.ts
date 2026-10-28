import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createSseParser, readSseStream } from '../src/lib/sse.ts';

test('events split across chunks are reassembled; several per chunk are all emitted', () => {
  const events: unknown[] = [];
  const parser = createSseParser((e) => events.push(e));
  parser.push('data: {"type":"log","mess');
  parser.push('age":"a"}\n');
  assert.equal(events.length, 0);
  parser.push('\ndata: {"type":"log","message":"b"}\n\ndata: {"type":"done"}\n\n');
  assert.deepEqual(events, [{ type: 'log', message: 'a' }, { type: 'log', message: 'b' }, { type: 'done' }]);
});

test('malformed JSON is skipped and an unterminated tail is flushed by end()', () => {
  const events: unknown[] = [];
  const parser = createSseParser((e) => events.push(e));
  parser.push('data: {oops}\n\ndata: {"type":"done"}');
  assert.deepEqual(events, []);
  parser.end();
  assert.deepEqual(events, [{ type: 'done' }]);
});

test('readSseStream decodes multi-byte UTF-8 split between chunks', async () => {
  const bytes = new TextEncoder().encode('data: {"message":"依頼_印刷"}\n\n');
  const cut = bytes.indexOf(0xe4) + 1; // inside the first 3-byte character
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(bytes.slice(0, cut));
      controller.enqueue(bytes.slice(cut));
      controller.close();
    },
  });
  const events: any[] = [];
  await readSseStream(body, (e) => events.push(e));
  assert.deepEqual(events, [{ message: '依頼_印刷' }]);
});
