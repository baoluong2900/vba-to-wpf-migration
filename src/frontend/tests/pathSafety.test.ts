import { test } from 'node:test';
import assert from 'node:assert/strict';

import { isSafeCliValue, isSafeName } from '../src/lib/pathSafety.ts';

test('Japanese and other real Access names are accepted', () => {
  for (const name of ['F_Login', 'AM依頼_印刷_PDF', 'C000_MAINⅡ', 'AM報告書(施工)_印刷_PDF', 'ALL', 'Q000 T LoginUser']) {
    assert.equal(isSafeName(name), true, name);
  }
});

test('separators, dot segments, drive prefixes, NUL and option-like names are rejected', () => {
  for (const name of ['', '.', '..', 'a/b', 'a\\b', '../etc', 'x..y', 'C:', 'c:\\temp', 'D:evil', 'a\u0000b', 'a\nb', '-h', '--fix']) {
    assert.equal(isSafeName(name), false, JSON.stringify(name));
  }
});

test('non-strings and overlong names are rejected', () => {
  assert.equal(isSafeName(undefined), false);
  assert.equal(isSafeName(42), false);
  assert.equal(isSafeName({ toString: () => 'F_Login' }), false);
  assert.equal(isSafeName('a'.repeat(256)), false);
});

test('CLI values: model ids pass, options and control characters do not', () => {
  assert.equal(isSafeCliValue('qwen3-coder-480b-a35b-instruct'), true);
  assert.equal(isSafeCliValue('meta-llama/llama-4-scout:17b'), true);
  assert.equal(isSafeCliValue('--input-only'), false);
  assert.equal(isSafeCliValue('model\r\nx'), false);
  assert.equal(isSafeCliValue(''), false);
  assert.equal(isSafeCliValue(['x']), false);
});
