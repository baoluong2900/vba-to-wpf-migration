import { test } from 'node:test';
import assert from 'node:assert/strict';

import { checkSameOrigin } from '../src/lib/originCheck.ts';

const host = '127.0.0.1:3000';

test('safe methods pass unless the browser marks them cross-site', () => {
  for (const method of ['GET', 'head', 'OPTIONS']) {
    assert.equal(checkSameOrigin({ method, secFetchSite: 'same-origin', host }).ok, true);
    assert.equal(checkSameOrigin({ method, origin: 'https://evil.test', host }).ok, true); // no Sec-Fetch-Site
    // e.g. <img src="http://127.0.0.1:3000/api/v1/layer2/models/health"> on another site
    assert.equal(checkSameOrigin({ method, secFetchSite: 'cross-site', host }).ok, false);
    assert.equal(checkSameOrigin({ method, secFetchSite: 'same-site', host }).ok, false);
  }
});

test('Sec-Fetch-Site decides when present', () => {
  assert.equal(checkSameOrigin({ method: 'POST', secFetchSite: 'same-origin', host }).ok, true);
  assert.equal(checkSameOrigin({ method: 'POST', secFetchSite: 'none', host }).ok, true);
  assert.equal(checkSameOrigin({ method: 'POST', secFetchSite: 'cross-site', origin: `http://${host}`, host }).ok, false);
  assert.equal(checkSameOrigin({ method: 'PUT', secFetchSite: 'same-site', host }).ok, false);
});

test('without Sec-Fetch-Site the Origin host must equal Host', () => {
  assert.equal(checkSameOrigin({ method: 'POST', origin: `http://${host}`, host }).ok, true);
  assert.equal(checkSameOrigin({ method: 'POST', origin: 'http://LOCALHOST:3000', host: 'localhost:3000' }).ok, true);
  assert.equal(checkSameOrigin({ method: 'POST', origin: 'http://192.168.1.20:3000', host }).ok, false);
  assert.equal(checkSameOrigin({ method: 'DELETE', origin: 'http://127.0.0.1:4000', host }).ok, false);
  assert.equal(checkSameOrigin({ method: 'POST', origin: 'null', host }).ok, false);
  assert.equal(checkSameOrigin({ method: 'POST', origin: `http://${host}`, host: null }).ok, false);
});

test('requests carrying neither header (curl, scripts) pass', () => {
  assert.equal(checkSameOrigin({ method: 'POST', secFetchSite: null, origin: null, host }).ok, true);
});

test('a blocked verdict explains why', () => {
  const verdict = checkSameOrigin({ method: 'POST', secFetchSite: 'cross-site', host });
  assert.equal(verdict.ok, false);
  if (!verdict.ok) assert.match(verdict.reason, /cross-site/);
});
