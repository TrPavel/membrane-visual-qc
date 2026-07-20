from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import http.client
import os
import socket
import ssl

import pytest

from membrane_vqc.pdbtm_errors import Stage4BError, Stage4BErrorCode
from membrane_vqc.pdbtm_transport import (
    PDBTM_HOST,
    PDBTM_PORT,
    PDBTM_USER_AGENT,
    PdbtmHttpsTransport,
    TransportPolicy,
    canonicalize_pdbtm_record_id,
)


class FakeHeaders:
    def __init__(self, pairs):
        self.pairs = list(pairs)

    def get_all(self, name, default=None):
        values = [value for key, value in self.pairs if key.lower() == name.lower()]
        return values if values else default


class FakeResponse:
    def __init__(self, body=b"{}", *, status=200, headers=None, read_hook=None):
        self.status = status
        self.headers = FakeHeaders(
            headers
            if headers is not None
            else [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
        )
        self._body = body
        self._position = 0
        self._read_hook = read_hook

    def getheaders(self):
        return list(self.headers.pairs)

    def read(self, amount):
        if self._read_hook is not None:
            self._read_hook()
        chunk = self._body[self._position : self._position + amount]
        self._position += len(chunk)
        return chunk


class FakeSocket:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)


class FakeContext:
    check_hostname = True
    verify_mode = ssl.CERT_REQUIRED


class FakeConnection:
    def __init__(self, response=None, *, connect_error=None, response_error=None, close_error=None):
        self.response = response or FakeResponse()
        self.connect_error = connect_error
        self.response_error = response_error
        self.close_error = close_error
        self.sock = FakeSocket()
        self.connected = False
        self.closed = False
        self.requests = []

    def connect(self):
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True

    def request(self, method, path, body=None, headers=None):
        self.requests.append((method, path, body, dict(headers or {})))

    def getresponse(self):
        if self.response_error is not None:
            raise self.response_error
        return self.response

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class Factory:
    def __init__(self, connection):
        self.connection = connection
        self.calls = []

    def __call__(self, host, port, **kwargs):
        self.calls.append((host, port, kwargs))
        return self.connection


class Token:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled

    def is_cancelled(self):
        return self.cancelled


def make_transport(connection, **kwargs):
    factory = Factory(connection)
    ssl_context_factory = kwargs.pop("ssl_context_factory", FakeContext)
    transport = PdbtmHttpsTransport(
        connection_factory=factory,
        ssl_context_factory=ssl_context_factory,
        utc_now=lambda: datetime(2026, 7, 20, 12, 34, 56, 123456, tzinfo=timezone.utc),
        **kwargs,
    )
    return transport, factory


def test_unsafe_injected_tls_context_is_rejected_before_connect():
    connection = FakeConnection()
    unsafe = FakeContext()
    unsafe.check_hostname = False
    transport, _ = make_transport(connection, ssl_context_factory=lambda: unsafe)

    with pytest.raises(Stage4BError) as caught:
        transport.fetch("1pcr", "pdbtm_json")
    assert caught.value.code is Stage4BErrorCode.TLS_ERROR
    assert not connection.connected


def test_close_failure_does_not_replace_successful_result():
    connection = FakeConnection(close_error=OSError("unsafe local diagnostic"))
    transport, _ = make_transport(connection)

    result = transport.fetch("1pcr", "pdbtm_json")
    assert result.body == b"{}"
    assert connection.closed


@pytest.mark.parametrize("value", ["1PCR", "1pCr", "9abc"])
def test_record_id_is_canonicalized(value):
    assert canonicalize_pdbtm_record_id(value) == value.lower()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "abc1",
        "1abc ",
        " 1abc",
        "1ab/c",
        "1ab\\c",
        "C:\\1abc",
        "//host/share",
        "1ab%63",
        "1abc?x",
        "1abc#x",
        "１abc",
        "1abé",
        b"1abc",
    ],
)
def test_record_id_rejects_every_noncanonical_shape(value):
    with pytest.raises(Stage4BError) as captured:
        canonicalize_pdbtm_record_id(value)  # type: ignore[arg-type]
    assert captured.value.code is Stage4BErrorCode.INVALID_RECORD_ID


@pytest.mark.parametrize(
    ("role", "path", "accept"),
    [
        ("pdbtm_json", "/api/v1/entry/1pcr.json", "application/json, text/plain"),
        ("transformed_pdb", "/api/v1/entry/1pcr.trpdb", "text/plain"),
    ],
)
def test_fixed_direct_request_and_evidence(role, path, accept, monkeypatch):
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.setenv(name, "http://user:secret@proxy.invalid:3128")
    body = b'{"id":"1pcr"}' if role == "pdbtm_json" else b"HEADER    1PCR\n"
    headers = [
        (
            "Content-Type",
            "application/json" if role == "pdbtm_json" else "text/plain; charset=UTF-8",
        ),
        ("Content-Length", str(len(body))),
        ("ETag", '"safe-tag"'),
        ("Last-Modified", "Sun, 19 Jul 2026 23:01:54 GMT"),
    ]
    connection = FakeConnection(FakeResponse(body, headers=headers))
    transport, factory = make_transport(connection)

    result = transport.fetch("1PCR", role)

    assert factory.calls[0][0:2] == (PDBTM_HOST, PDBTM_PORT)
    assert factory.calls[0][2]["timeout"] == 5.0
    assert "context" in factory.calls[0][2]
    assert connection.requests == [
        (
            "GET",
            path,
            None,
            {
                "Host": PDBTM_HOST,
                "Accept": accept,
                "Accept-Encoding": "identity",
                "User-Agent": PDBTM_USER_AGENT,
                "Connection": "close",
            },
        )
    ]
    assert not hasattr(connection, "tunnel_host")
    assert result.record_id == "1pcr"
    assert result.body == body
    assert result.evidence.requested_url == f"https://{PDBTM_HOST}{path}"
    assert result.evidence.final_url == result.evidence.requested_url
    assert result.evidence.sha256 == hashlib.sha256(body).hexdigest()
    assert result.evidence.byte_size == len(body)
    assert result.sha256 == result.evidence.sha256
    assert result.byte_size == result.evidence.byte_size
    assert result.evidence.tls_verified is True
    assert result.evidence.etag == '"safe-tag"'
    assert result.evidence.requested_at == "2026-07-20T12:34:56.123456Z"
    assert connection.closed


def test_invalid_role_never_opens_connection():
    connection = FakeConnection()
    transport, factory = make_transport(connection)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "wrong")
    assert captured.value.code is Stage4BErrorCode.PROVIDER_RESPONSE_INVALID
    assert factory.calls == []


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (301, Stage4BErrorCode.REDIRECT_DISALLOWED),
        (307, Stage4BErrorCode.REDIRECT_DISALLOWED),
        (407, Stage4BErrorCode.PROXY_UNSUPPORTED),
        (404, Stage4BErrorCode.PROVIDER_NOT_FOUND),
        (408, Stage4BErrorCode.NETWORK_TIMEOUT),
        (429, Stage4BErrorCode.PROVIDER_RATE_LIMITED),
        (500, Stage4BErrorCode.PROVIDER_SERVER_ERROR),
        (599, Stage4BErrorCode.PROVIDER_SERVER_ERROR),
        (201, Stage4BErrorCode.PROVIDER_RESPONSE_INVALID),
    ],
)
def test_status_mapping_does_not_read_error_body(status, code):
    def forbidden_read():
        raise AssertionError("error response body must not be read")

    connection = FakeConnection(
        FakeResponse(b"secret html", status=status, read_hook=forbidden_read)
    )
    transport, _ = make_transport(connection)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")
    assert captured.value.code is code
    assert "secret" not in str(captured.value)
    assert connection.closed


@pytest.mark.parametrize(
    ("headers", "role"),
    [
        ([], "pdbtm_json"),
        (
            [("Content-Type", "application/json"), ("Content-Type", "application/json")],
            "pdbtm_json",
        ),
        ([("Content-Type", "text/html; charset=UTF-8")], "pdbtm_json"),
        ([("Content-Type", "text/plain")], "pdbtm_json"),
        ([("Content-Type", "application/json; charset=latin-1")], "pdbtm_json"),
        ([("Content-Type", "application/json; charset=UTF-8")], "transformed_pdb"),
        ([("Content-Type", "application/json; boundary=x")], "pdbtm_json"),
        ([("Content-Type", "application/json"), ("Content-Encoding", "gzip")], "pdbtm_json"),
        (
            [
                ("Content-Type", "application/json"),
                ("Content-Encoding", "identity"),
                ("Content-Encoding", "identity"),
            ],
            "pdbtm_json",
        ),
        ([("Content-Type", "application/json"), ("Transfer-Encoding", "gzip")], "pdbtm_json"),
        (
            [
                ("Content-Type", "application/json"),
                ("Transfer-Encoding", "chunked"),
                ("Content-Length", "2"),
            ],
            "pdbtm_json",
        ),
        ([("Content-Type", "application/json"), ("Content-Length", "+2")], "pdbtm_json"),
        (
            [
                ("Content-Type", "application/json"),
                ("Content-Length", "2"),
                ("Content-Length", "2"),
            ],
            "pdbtm_json",
        ),
    ],
)
def test_ambiguous_or_unsupported_response_headers_are_rejected(headers, role):
    connection = FakeConnection(FakeResponse(b"{}", headers=headers))
    transport, _ = make_transport(connection)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", role)
    assert captured.value.code is Stage4BErrorCode.PROVIDER_RESPONSE_INVALID


@pytest.mark.parametrize("encoding", [None, "identity", "IDENTITY"])
def test_identity_content_encoding_is_recorded_without_decompression(encoding):
    headers = [("Content-Type", "application/json"), ("Content-Length", "2")]
    if encoding is not None:
        headers.append(("Content-Encoding", encoding))
    connection = FakeConnection(FakeResponse(b"{}", headers=headers))
    transport, _ = make_transport(connection)
    result = transport.fetch("1pcr", "pdbtm_json")
    assert result.evidence.content_encoding == ("identity" if encoding else None)


@pytest.mark.parametrize("name", ["ETag", "Last-Modified"])
@pytest.mark.parametrize("value", ["x" * 1025, "safe\tunsafe", "café"])
def test_unsafe_optional_evidence_header_is_rejected(name, value):
    headers = [("Content-Type", "application/json"), (name, value)]
    connection = FakeConnection(FakeResponse(b"{}", headers=headers))
    transport, _ = make_transport(connection)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")
    assert captured.value.code is Stage4BErrorCode.PROVIDER_RESPONSE_INVALID


def test_declared_and_streamed_size_limits_are_enforced():
    policy = TransportPolicy(read_chunk_bytes=2, max_response_bytes=3, max_pair_bytes=6)
    declared = FakeConnection(
        FakeResponse(b"", headers=[("Content-Type", "application/json"), ("Content-Length", "4")])
    )
    transport, _ = make_transport(declared, policy=policy)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")
    assert captured.value.code is Stage4BErrorCode.RESPONSE_TOO_LARGE

    streamed = FakeConnection(FakeResponse(b"1234", headers=[("Content-Type", "application/json")]))
    transport, _ = make_transport(streamed, policy=policy)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")
    assert captured.value.code is Stage4BErrorCode.RESPONSE_TOO_LARGE


def test_short_declared_body_is_invalid():
    connection = FakeConnection(
        FakeResponse(b"{}", headers=[("Content-Type", "application/json"), ("Content-Length", "3")])
    )
    transport, _ = make_transport(connection)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")
    assert captured.value.code is Stage4BErrorCode.PROVIDER_RESPONSE_INVALID


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (socket.timeout("private timeout detail"), Stage4BErrorCode.NETWORK_TIMEOUT),
        (ssl.SSLError("private tls detail"), Stage4BErrorCode.TLS_ERROR),
        (OSError("private host and proxy detail"), Stage4BErrorCode.NETWORK_UNAVAILABLE),
        (http.client.BadStatusLine("secret line"), Stage4BErrorCode.PROVIDER_RESPONSE_INVALID),
    ],
)
def test_network_exceptions_are_mapped_and_redacted(error, code):
    connection = FakeConnection(connect_error=error)
    transport, _ = make_transport(connection)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")
    assert captured.value.code is code
    assert "private" not in str(captured.value)
    assert "secret" not in str(captured.value)


def test_cancellation_before_network_and_during_read_wins():
    token = Token(cancelled=True)
    connection = FakeConnection()
    transport, factory = make_transport(connection)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json", cancellation=token)
    assert captured.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED
    assert factory.calls == []

    token = Token()

    def cancel_on_read():
        token.cancelled = True

    connection = FakeConnection(FakeResponse(b"{}", read_hook=cancel_on_read))
    transport, _ = make_transport(connection)
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json", cancellation=token)
    assert captured.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED


def test_cancellation_observed_with_network_exception_takes_precedence():
    token = Token()

    class CancellingConnection(FakeConnection):
        def connect(self):
            token.cancelled = True
            raise OSError("must be hidden")

    transport, _ = make_transport(CancellingConnection())
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json", cancellation=token)
    assert captured.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED


def test_response_and_pair_deadlines_are_enforced():
    ticks = iter([0.0, 0.0, 0.0, 0.0, 2.0])
    connection = FakeConnection()
    transport, _ = make_transport(
        connection,
        policy=TransportPolicy(
            connect_timeout=1,
            read_timeout=1,
            response_timeout=1,
            pair_timeout=2,
        ),
        monotonic=lambda: next(ticks),
    )
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")
    assert captured.value.code is Stage4BErrorCode.NETWORK_TIMEOUT

    ticks = iter([10.0, 10.0])
    transport, factory = make_transport(FakeConnection(), monotonic=lambda: next(ticks))
    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json", pair_deadline=9.0)
    assert captured.value.code is Stage4BErrorCode.NETWORK_TIMEOUT
    assert factory.calls == []


def test_error_contract_is_stable_and_boolean():
    error = Stage4BError(Stage4BErrorCode.NETWORK_UNAVAILABLE)
    assert error.code.value == "NETWORK_UNAVAILABLE"
    assert error.user_message == "The PDBTM service is currently unreachable."
    assert error.retryable is True
    assert error.existing_cache_usable is True
    assert str(error) == error.user_message


def test_transport_does_not_consult_proxy_environment(monkeypatch):
    def forbidden_getenv(*args, **kwargs):
        raise AssertionError("proxy environment must not be consulted")

    monkeypatch.setattr(os, "getenv", forbidden_getenv)
    connection = FakeConnection()
    transport, _ = make_transport(connection)
    transport.fetch("1pcr", "pdbtm_json")
