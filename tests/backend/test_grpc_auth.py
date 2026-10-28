"""Shared-token authentication for the gRPC gateway (src/backend/api_gateway/auth.py)."""
from __future__ import annotations

import shutil
import subprocess
from concurrent import futures

import grpc
import pytest

from api_gateway.auth import TokenAuthInterceptor, build_interceptors, server_credentials

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


@pytest.fixture(scope="module")
def tls_files(tmp_path_factory):
    """A throwaway self-signed certificate for localhost, made with the openssl CLI."""
    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("openssl is not installed")
    folder = tmp_path_factory.mktemp("tls")
    cert, key = folder / "gateway.pem", folder / "gateway.key"
    subprocess.run(
        [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
         "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1", "-keyout", str(key), "-out", str(cert)],
        check=True, capture_output=True,
    )
    return cert, key


def test_tls_is_off_unless_both_files_are_configured():
    assert server_credentials("", "") is None
    for cert, key in (("gateway.pem", ""), ("", "gateway.key")):
        with pytest.raises(ValueError):
            server_credentials(cert, key)  # never fall back to plaintext when TLS was asked for


def test_relative_tls_paths_resolve_from_the_base_dir(tls_files):
    cert, key = tls_files
    assert server_credentials(cert.name, key.name, base_dir=cert.parent) is not None
    with pytest.raises(FileNotFoundError):
        server_credentials(cert.name, key.name, base_dir=cert.parent / "elsewhere")


def test_tls_gateway_serves_trusting_clients_only(tls_files):
    cert, key = tls_files
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2), interceptors=build_interceptors(TOKEN))
    server.add_generic_rpc_handlers((_EchoService(),))
    port = server.add_secure_port("127.0.0.1:0", server_credentials(str(cert), str(key)))
    server.start()
    auth = [("authorization", f"Bearer {TOKEN}")]
    try:
        trusting = grpc.ssl_channel_credentials(root_certificates=cert.read_bytes())
        with grpc.secure_channel(f"127.0.0.1:{port}", trusting) as ch:
            assert _call(ch, auth) == b"ping"
            with pytest.raises(grpc.RpcError) as exc:
                _call(ch)  # TLS does not replace the token
            assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED
        with grpc.insecure_channel(f"127.0.0.1:{port}") as ch:
            with pytest.raises(grpc.RpcError) as exc:
                _call(ch, auth)
            assert exc.value.code() == grpc.StatusCode.UNAVAILABLE
    finally:
        server.stop(None)
