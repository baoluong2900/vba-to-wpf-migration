import { test } from 'node:test';
import assert from 'node:assert/strict';

import { contentDisposition } from '../src/lib/contentDisposition.ts';
import { layer4DownloadUrl } from '../src/lib/downloadUrl.ts';

test('ASCII names keep a readable filename and an RFC 5987 copy', () => {
  assert.equal(contentDisposition('F_Login.xlsx'), `attachment; filename="F_Login.xlsx"; filename*=UTF-8''F_Login.xlsx`);
});

test('Japanese names produce a Latin-1-safe header Headers.set accepts', () => {
  const value = contentDisposition('AM報告書(施工)_印刷_PDF.xlsx');
  assert.equal(
    value,
    `attachment; filename="AM___(__)____PDF.xlsx"; filename*=UTF-8''AM%E5%A0%B1%E5%91%8A%E6%9B%B8%28%E6%96%BD%E5%B7%A5%29_%E5%8D%B0%E5%88%B7_PDF.xlsx`,
  );
  assert.doesNotThrow(() => new Headers().set('Content-Disposition', value));
  assert.equal(decodeURIComponent(value.split("UTF-8''")[1]), 'AM報告書(施工)_印刷_PDF.xlsx');
});

test('quotes, backslashes and CR/LF cannot break out of the header', () => {
  const value = contentDisposition('a"b\\c\r\nSet-Cookie: x.xlsx');
  assert.ok(!/[\r\n]/.test(value));
  assert.match(value, /^attachment; filename="a_b_c__Set-Cookie: x\.xlsx"; filename\*=UTF-8''/);
  assert.doesNotThrow(() => new Headers().set('Content-Disposition', value));
});

test('download URLs percent-encode every segment', () => {
  assert.equal(
    layer4DownloadUrl('BD', 'screen', 'C000_MAINⅡ #1?.xlsx'),
    '/api/v1/layer4/download/BD/screen/C000_MAIN%E2%85%A1%20%231%3F.xlsx',
  );
});
