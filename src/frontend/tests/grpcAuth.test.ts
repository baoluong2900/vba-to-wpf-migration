import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as grpc from '@grpc/grpc-js';

import { bearerAuthInterceptor } from '../src/lib/grpcAuth.ts';

test('the interceptor adds a bearer authorization header to the outgoing metadata', () => {
  let sent: grpc.Metadata | undefined;
  const nextCall = {
    start(metadata: grpc.Metadata) { sent = metadata; },
    sendMessageWithContext() {},
    sendMessage() {},
    startRead() {},
    halfClose() {},
    cancelWithStatus() {},
    getPeer() { return ''; },
    getAuthContext() { return null; },
  };
  const call = bearerAuthInterceptor('s3cret')({} as any, () => nextCall as any);
  const metadata = new grpc.Metadata();
  metadata.set('x-trace', '1');
  call.start(metadata, {});
  assert.deepEqual(sent?.get('authorization'), ['Bearer s3cret']);
  assert.deepEqual(sent?.get('x-trace'), ['1']);
});
