import { test } from 'node:test';
import assert from 'node:assert/strict';

import { logicCodeStatus, summarizeLogicMethods } from '../src/lib/logicSummary.ts';

const methods = [
  { status: 'success', code: 'Username = "";' },
  { status: 'success', code: '// TODO: port DLookup' },
  { status: 'success', code: 'throw new NotImplementedException();' },
  { status: 'skipped', code: '// Skipped' },
  { status: 'error' },
];

test('method statuses map to the console codes', () => {
  assert.deepEqual(methods.map(logicCodeStatus), ['DONE', 'TODO', 'TODO', 'SKIP', 'ERROR']);
});

test('summary counts each status; compile_ok needs exit 0, no errors and no TODOs', () => {
  assert.deepEqual(summarizeLogicMethods(methods, 1), { done: 1, todo: 2, skip: 1, error: 1, compile_ok: false });
  assert.equal(summarizeLogicMethods([methods[0], methods[3]], 0).compile_ok, true);
  assert.equal(summarizeLogicMethods([methods[0]], 1).compile_ok, false);
  assert.equal(summarizeLogicMethods([methods[1]], 0).compile_ok, false);
});
