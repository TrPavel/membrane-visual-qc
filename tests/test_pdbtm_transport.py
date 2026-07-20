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

    def isclosed(self):
        """Mirror http.client.HTTPResponse.isclosed(): true once every byte
        of the fake body has been delivered, matching real behavior where
        the terminal chunk/declared length closes the response during the
        read call that consumes the last byte -- no separate empty read is
        needed to detect it."""

        return self._position >= len(self._body)


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


class NoSocketAfterConnectConnection(FakeConnection):
    """Simulates connect() completing without ever populating .sock."""

    def connect(self):
        super().connect()
        self.sock = None


class OwnershipTransferConnection(FakeConnection):
    """Models real http.client.HTTPConnection.getresponse() behavior for a
    will-close response: connection.sock is nulled and ownership of the
    still-live socket is effectively handed to the response, exactly like
    CPython's stdlib does whenever Connection: close applies (which this
    transport always sends)."""

    def getresponse(self):
        response = super().getresponse()
        self.sock = None
        return response


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


class FakeClock:
    """A deterministic, manually advanced monotonic clock for deadline tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, amount: float) -> None:
        self.now += amount


class ClockAdvancingConnection(FakeConnection):
    """A FakeConnection whose getresponse() call consumes simulated wall time."""

    def __init__(self, *args, clock=None, advance_on_getresponse=0.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._clock = clock
        self._advance_on_getresponse = advance_on_getresponse

    def getresponse(self):
        if self._clock is not None:
            self._clock.advance(self._advance_on_getresponse)
        return super().getresponse()


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
    policy = TransportPolicy(read_chunk_bytes=2, max_response_bytes=3)
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


def test_set_read_timeout_clamps_to_remaining_not_full_read_timeout():
    """A phase beginning near the deadline must not receive the full inactivity timeout."""

    clock = FakeClock(14.95)
    policy = TransportPolicy(read_timeout=15)
    transport, _ = make_transport(FakeConnection(), policy=policy, monotonic=clock)
    connection = FakeConnection()

    transport._set_read_timeout(connection.sock, deadline=15.0)

    assert connection.sock.timeouts == [pytest.approx(0.05)]


def test_read_timeout_shrinks_before_getresponse_and_every_chunk_read():
    clock = FakeClock(0.0)
    policy = TransportPolicy(
        connect_timeout=5,
        read_timeout=15,
        response_timeout=15,
        read_chunk_bytes=4,
        max_response_bytes=1024,
    )
    body = b"0123456789"

    def on_read():
        clock.advance(3.0)

    response = FakeResponse(
        body,
        headers=[("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
        read_hook=on_read,
    )
    connection = ClockAdvancingConnection(response, clock=clock, advance_on_getresponse=2.0)
    transport, _ = make_transport(connection, policy=policy, monotonic=clock)

    result = transport.fetch("1pcr", "pdbtm_json")

    assert result.body == body
    timeouts = connection.sock.timeouts
    # One shrink call before request, one before getresponse, and one before
    # each of the three data-chunk reads -- never a stale, once-computed
    # value reused across phases. No fourth "detect EOF" call is made: once
    # the last chunk is consumed, response.isclosed() is already true, so
    # the loop breaks without touching the socket again (see the regression
    # this guards: touching a will-close connection's socket after the body
    # is fully drained is not guaranteed safe).
    assert len(timeouts) == 5
    assert all(earlier >= later for earlier, later in zip(timeouts, timeouts[1:]))
    # getresponse() alone consumed 2s, so the first read-loop timeout must
    # already be smaller than the full configured read_timeout.
    assert timeouts[2] < policy.read_timeout
    # by the final chunk almost the entire response_timeout has elapsed, so
    # the remaining budget is a small fraction of the nominal read_timeout.
    assert timeouts[-1] < policy.read_timeout / 2


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


def test_socket_absent_immediately_after_connect_is_network_unavailable():
    connection = NoSocketAfterConnectConnection()
    transport, factory = make_transport(connection)

    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")

    assert captured.value.code is Stage4BErrorCode.NETWORK_UNAVAILABLE
    assert connection.connected
    assert connection.requests == []


def test_connection_close_ownership_transfer_still_reads_full_body():
    """Regression test for the confirmed Stage 4B1 defect: the request always
    sends Connection: close, so real http.client.HTTPConnection.getresponse()
    nulls connection.sock and hands the still-live socket to the response
    before the body is read. The transport must use the socket it captured
    right after connect(), not re-read connection.sock, or every real fetch
    would fail with a spurious NETWORK_UNAVAILABLE despite a fully valid,
    fully readable HTTP response."""

    body = b'{"id":"1pcr"}'
    headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
    connection = OwnershipTransferConnection(FakeResponse(body, headers=headers))
    transport, _ = make_transport(connection)

    result = transport.fetch("1pcr", "pdbtm_json")

    assert result.body == body
    assert result.byte_size == len(body)
    assert result.sha256 == hashlib.sha256(body).hexdigest()
    # Confirms the fake genuinely exercised the ownership-transfer scenario.
    assert connection.sock is None


def test_shrinking_timeout_is_applied_to_the_captured_socket_after_ownership_transfer():
    policy = TransportPolicy(read_chunk_bytes=4, max_response_bytes=1024)
    body = b"0123456789"
    headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
    connection = OwnershipTransferConnection(FakeResponse(body, headers=headers))
    captured_before_fetch = connection.sock  # same object production code will capture
    transport, _ = make_transport(connection, policy=policy)

    result = transport.fetch("1pcr", "pdbtm_json")

    assert result.body == body
    assert connection.sock is None
    # before request, before getresponse, and one per real chunk (4, 4, 2
    # bytes) -- no extra call after the body is fully drained.
    assert len(captured_before_fetch.timeouts) == 5


def test_timeout_during_body_read_after_ownership_transfer_maps_to_network_timeout():
    def raise_timeout():
        raise socket.timeout("private detail")

    body = b"0123456789"
    headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
    response = FakeResponse(body, headers=headers, read_hook=raise_timeout)
    connection = OwnershipTransferConnection(response)
    transport, _ = make_transport(connection)

    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")

    assert captured.value.code is Stage4BErrorCode.NETWORK_TIMEOUT
    assert "private" not in str(captured.value)


def test_cancellation_still_wins_after_ownership_transfer():
    token = Token()

    def cancel_on_read():
        token.cancelled = True

    body = b"0123456789"
    headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
    response = FakeResponse(body, headers=headers, read_hook=cancel_on_read)
    connection = OwnershipTransferConnection(response)
    transport, _ = make_transport(connection)

    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json", cancellation=token)

    assert captured.value.code is Stage4BErrorCode.RETRIEVAL_CANCELLED


def test_streamed_size_limit_still_enforced_after_ownership_transfer():
    policy = TransportPolicy(read_chunk_bytes=2, max_response_bytes=3)
    response = FakeResponse(b"1234", headers=[("Content-Type", "application/json")])
    connection = OwnershipTransferConnection(response)
    transport, _ = make_transport(connection, policy=policy)

    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")

    assert captured.value.code is Stage4BErrorCode.RESPONSE_TOO_LARGE


def test_declared_size_limit_still_enforced_after_ownership_transfer():
    policy = TransportPolicy(max_response_bytes=3)
    response = FakeResponse(
        b"", headers=[("Content-Type", "application/json"), ("Content-Length", "4")]
    )
    connection = OwnershipTransferConnection(response)
    transport, _ = make_transport(connection, policy=policy)

    with pytest.raises(Stage4BError) as captured:
        transport.fetch("1pcr", "pdbtm_json")

    assert captured.value.code is Stage4BErrorCode.RESPONSE_TOO_LARGE
