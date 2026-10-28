import { test } from 'node:test';
import assert from 'node:assert/strict';

import { resolvePython } from '../src/lib/python.ts';

const only = (...files: string[]) => (file: string) => files.includes(file);

test('PYTHON_BIN wins', () => {
  assert.equal(
    resolvePython({ env: { PYTHON_BIN: ' /opt/venv/bin/python ', PATH: '/usr/bin' }, platform: 'darwin', isExecutable: only('/usr/bin/python3') }),
    '/opt/venv/bin/python',
  );
});

test('python3 on PATH is preferred over python', () => {
  assert.equal(
    resolvePython({ env: { PATH: '/a:/b' }, platform: 'linux', isExecutable: only('/a/python', '/b/python3') }),
    '/b/python3',
  );
  assert.equal(resolvePython({ env: { PATH: '/a' }, platform: 'linux', isExecutable: only('/a/python') }), '/a/python');
});

test('falls back to known install locations, then to a bare name', () => {
  assert.equal(
    resolvePython({ env: { PATH: '/nothing' }, platform: 'darwin', isExecutable: only('/opt/homebrew/bin/python3') }),
    '/opt/homebrew/bin/python3',
  );
  assert.equal(resolvePython({ env: {}, platform: 'darwin', isExecutable: () => false }), 'python3');
});

test('Windows: Path key in any case, .exe names, Store alias stubs skipped', () => {
  const env = { Path: 'C:\\Users\\me\\AppData\\Local\\Microsoft\\WindowsApps;C:\\Python312' };
  assert.equal(
    resolvePython({
      env,
      platform: 'win32',
      isExecutable: only('C:\\Users\\me\\AppData\\Local\\Microsoft\\WindowsApps\\python3.exe', 'C:\\Python312\\python.exe'),
    }),
    'C:\\Python312\\python.exe',
  );
  assert.equal(resolvePython({ env: { Path: 'C:\\nope' }, platform: 'win32', isExecutable: () => false }), 'python');
});
