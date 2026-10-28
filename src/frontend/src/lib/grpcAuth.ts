import * as grpc from '@grpc/grpc-js';

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
