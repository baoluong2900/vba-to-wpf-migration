import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';

import { PROTO_PATH, resolveWorkflowRoot } from '../src/lib/paths.ts';

const marker = (root: string) => (file: string) => file === path.join(root, 'src', 'backend', 'protos', 'workflow.proto');

test('VBA_BRAIN_ROOT overrides everything', () => {
  assert.equal(resolveWorkflowRoot({ VBA_BRAIN_ROOT: '/srv/workflow' }, '/somewhere', () => false), path.resolve('/srv/workflow'));
});

test('found from src/frontend (the normal cwd) and from the repo root', () => {
  const root = path.resolve('/repo/workflow');
  assert.equal(resolveWorkflowRoot({}, path.join(root, 'src', 'frontend'), marker(root)), root);
  assert.equal(resolveWorkflowRoot({}, root, marker(root)), root);
});

test('falls back to two levels above cwd when nothing is found', () => {
  assert.equal(resolveWorkflowRoot({}, path.resolve('/x/y/z'), () => false), path.resolve('/x'));
});

test('in this checkout the proto resolves', async () => {
  const fs = await import('node:fs');
  assert.equal(fs.existsSync(PROTO_PATH), true, PROTO_PATH);
});
