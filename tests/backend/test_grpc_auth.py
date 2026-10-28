"""Shared-token authentication for the gRPC gateway (src/backend/api_gateway/auth.py)."""
from __future__ import annotations

from concurrent import futures

import grpc
import pytest

from api_gateway.auth import TokenAuthInterceptor, build_interceptors

TOKEN = "s3cret-token"
METHOD = "/test.Echo/Say"


def _echo(request: bytes, context) -> bytes:
    return request


class _EchoService(grpc.GenericRpcHandler):
    def service(self, handler_call_details):
        if handler_call_details.method == METHOD:
            return grpc.unary_unary_rpc_method_handler(_echo)
        return None


@pytest.fixture()
def channel():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=2),
        interceptors=build_interceptors(TOKEN),
    )
    server.add_generic_rpc_handlers((_EchoService(),))
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    with grpc.insecure_channel(f"127.0.0.1:{port}") as ch:
        yield ch
    server.stop(None)


def _call(channel, metadata=None) -> bytes:
    return channel.unary_unary(METHOD)(b"ping", metadata=metadata, timeout=5)


def test_valid_token_is_accepted(channel):
    assert _call(channel, [("authorization", f"Bearer {TOKEN}")]) == b"ping"


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        [("authorization", "Bearer wrong")],
        [("authorization", TOKEN)],  # missing "Bearer " prefix
        [("x-api-key", TOKEN)],
    ],
)
def test_missing_or_wrong_token_is_rejected(channel, metadata):
    with pytest.raises(grpc.RpcError) as exc:
        _call(channel, metadata)
    assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_unknown_method_is_still_unimplemented(channel):
    with pytest.raises(grpc.RpcError) as exc:
        channel.unary_unary("/test.Echo/Missing")(b"", metadata=[("authorization", f"Bearer {TOKEN}")], timeout=5)
    assert exc.value.code() == grpc.StatusCode.UNIMPLEMENTED


def test_no_token_means_no_interceptor():
    assert build_interceptors("") == []


def test_empty_token_is_rejected_at_construction():
    with pytest.raises(ValueError):
        TokenAuthInterceptor("")


def test_metadata_key_is_case_insensitive():
    interceptor = TokenAuthInterceptor(TOKEN)
    assert interceptor.is_authorized([("Authorization", f"Bearer {TOKEN}")])
    assert not interceptor.is_authorized([("authorization", f"Bearer {TOKEN}x")])
