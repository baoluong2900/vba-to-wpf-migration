import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as grpc from '@grpc/grpc-js';

import { bearerAuthInterceptor, channelCredentials } from '../src/lib/grpcAuth.ts';

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

test('the gateway channel is plaintext unless TLS is configured', () => {
  assert.equal(channelCredentials({})._isSecure(), false);
  assert.equal(channelCredentials({ GRPC_TLS: '1' })._isSecure(), true);
  assert.equal(channelCredentials({ GRPC_TLS: 'true' })._isSecure(), true);
});

test('GRPC_TLS_CA is read as the certificate to trust', () => {
  assert.throws(() => channelCredentials({ GRPC_TLS_CA: '/nonexistent/gateway.pem' }), /ENOENT/);
});
