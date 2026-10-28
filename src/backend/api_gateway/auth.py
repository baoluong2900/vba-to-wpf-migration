"""
api_gateway/auth.py — Optional shared-token authentication and TLS for the gRPC gateway.

When a token is configured (env ``GRPC_AUTH_TOKEN`` or ``config.json → grpc.auth_token``),
every RPC must carry the metadata header ``authorization: Bearer <token>``; anything else is
rejected with ``UNAUTHENTICATED`` before it reaches a servicer. With no token configured the
interceptor is not installed, so local development keeps working unchanged.

The Next.js console attaches the header automatically (``src/frontend/src/app/api/grpcClient.ts``)
when the same ``GRPC_AUTH_TOKEN`` is present in its environment.

With ``GRPC_TLS_CERT`` and ``GRPC_TLS_KEY`` set, the gateway serves TLS only; the console then
needs ``GRPC_TLS_CA`` (the PEM file to trust) or ``GRPC_TLS=1`` (system roots).
"""
from __future__ import annotations

import hmac
from pathlib import Path
from typing import Callable, Optional

import grpc

AUTH_METADATA_KEY = "authorization"
_BEARER_PREFIX = "Bearer "


def _deny(request, context: grpc.ServicerContext):
    context.abort(grpc.StatusCode.UNAUTHENTICATED, "missing or invalid bearer token")


def _deny_handler(handler: grpc.RpcMethodHandler) -> grpc.RpcMethodHandler:
    """Build a rejecting handler of the same streaming shape as the real one."""
    if handler.request_streaming and handler.response_streaming:
        return grpc.stream_stream_rpc_method_handler(_deny)
    if handler.request_streaming:
        return grpc.stream_unary_rpc_method_handler(_deny)
    if handler.response_streaming:
        return grpc.unary_stream_rpc_method_handler(_deny)
    return grpc.unary_unary_rpc_method_handler(_deny)


class TokenAuthInterceptor(grpc.ServerInterceptor):
    """Reject every call whose ``authorization`` metadata is not ``Bearer <token>``."""

    def __init__(self, token: str):
        if not token:
            raise ValueError("TokenAuthInterceptor requires a non-empty token")
        self._expected = (_BEARER_PREFIX + token).encode("utf-8")

    def is_authorized(self, metadata) -> bool:
        supplied = ""
        for key, value in metadata or ():
            if key.lower() == AUTH_METADATA_KEY:
                supplied = value if isinstance(value, str) else value.decode("utf-8", "replace")
                break
        # Constant-time comparison so the token can't be recovered from response timing.
        return hmac.compare_digest(supplied.encode("utf-8"), self._expected)

    def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Optional[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> Optional[grpc.RpcMethodHandler]:
        handler = continuation(handler_call_details)
        if handler is None or self.is_authorized(handler_call_details.invocation_metadata):
            return handler
        return _deny_handler(handler)


def build_interceptors(token: str) -> list[grpc.ServerInterceptor]:
    """Interceptors to install on the server — empty when no token is configured."""
    return [TokenAuthInterceptor(token)] if token else []


def server_credentials(cert_file: str, key_file: str, base_dir: Path | None = None) -> grpc.ServerCredentials | None:
    """
    TLS credentials from a PEM certificate chain and private key (relative paths resolved from
    ``base_dir``), or None — plaintext — when neither is configured. Only one of them is a
    configuration error: falling back to plaintext would silently drop the protection asked for.
    """
    if not cert_file and not key_file:
        return None
    if not cert_file or not key_file:
        raise ValueError("GRPC_TLS_CERT and GRPC_TLS_KEY must be set together (or both left empty)")
    cert_path, key_path = (Path(base_dir or ".") / p for p in (cert_file, key_file))
    return grpc.ssl_server_credentials([(key_path.read_bytes(), cert_path.read_bytes())])
