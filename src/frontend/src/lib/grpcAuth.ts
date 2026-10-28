import { readFileSync } from 'node:fs';
import * as grpc from '@grpc/grpc-js';

/**
 * Channel credentials for the gateway: TLS when `GRPC_TLS_CA` names the PEM file to trust (the
 * gateway's own certificate when it is self-signed) or `GRPC_TLS=1` trusts the system roots;
 * plaintext otherwise, matching a gateway without `GRPC_TLS_CERT` / `GRPC_TLS_KEY`.
 */
export function channelCredentials(env: Record<string, string | undefined> = process.env): grpc.ChannelCredentials {
  if (env.GRPC_TLS_CA) return grpc.credentials.createSsl(readFileSync(env.GRPC_TLS_CA));
  if (env.GRPC_TLS === '1' || env.GRPC_TLS === 'true') return grpc.credentials.createSsl();
  return grpc.credentials.createInsecure();
}

/** Client interceptor that sends `authorization: Bearer <token>` metadata on every RPC. */
export function bearerAuthInterceptor(token: string): grpc.Interceptor {
  return (options, nextCall) =>
    new grpc.InterceptingCall(nextCall(options), {
      start(metadata, listener, next) {
        metadata.set('authorization', `Bearer ${token}`);
        next(metadata, listener);
      },
    });
}
