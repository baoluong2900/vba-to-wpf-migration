import { test } from 'node:test';
import assert from 'node:assert/strict';

import { staticSqlCheck } from '../src/app/api/v1/layer3/staticSqlCheck.ts';

test('clean PostgreSQL passes and says nothing was executed', () => {
  const res = staticSqlCheck("SELECT COALESCE(name, '') FROM tbl_users WHERE id = :id LIMIT 10");
  assert.equal(res.success, true);
  assert.equal(res.preview, true);
  assert.match(res.message ?? '', /not executed/);
});

test('empty SQL fails', () => {
  assert.equal(staticSqlCheck('   ').error_code, '42601');
});

test('Access functions are reported as undefined functions', () => {
  for (const sql of ['SELECT IIf(a > 1, 1, 0) FROM t', 'SELECT Nz(x, 0) FROM t', "SELECT DLookup('a', 'b') FROM t", 'SELECT Len (x) FROM t']) {
    const res = staticSqlCheck(sql);
    assert.equal(res.success, false, sql);
    assert.equal(res.error_code, '42883', sql);
  }
});

test('function names inside strings, comments or identifiers do not trip the check', () => {
  assert.equal(staticSqlCheck("SELECT 'IIf(a)' AS label, tariff FROM t -- Nz(x) later\n/* DLookup( */").success, true);
});

test("escaped quotes are fine, unterminated literals are not", () => {
  assert.equal(staticSqlCheck("SELECT 'it''s' FROM t").success, true);
  assert.equal(staticSqlCheck("SELECT 'oops FROM t").error_code, '42601');
  assert.equal(staticSqlCheck("SELECT 'a'' FROM t").error_code, '42601');
});

test('unbalanced parentheses fail', () => {
  assert.equal(staticSqlCheck('SELECT (1 FROM t').success, false);
  assert.equal(staticSqlCheck('SELECT 1) FROM (t').success, false);
});

test('other Access-only syntax fails', () => {
  for (const sql of [
    'SELECT DISTINCTROW a FROM t',
    'SELECT TOP 5 a FROM t',
    'SELECT a FROM t WHERE d > #2024-01-31#',
    'SELECT a FROM t WHERE id = [Forms]![F_Login]![txtID]',
  ]) {
    assert.equal(staticSqlCheck(sql).error_code, '42601', sql);
  }
});
