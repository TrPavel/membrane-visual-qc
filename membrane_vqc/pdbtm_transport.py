"""Direct, bounded HTTPS transport for the reviewed PDBTM API-v1 endpoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import re
import socket
import ssl
import time
from typing import Protocol

from .pdbtm_errors import Stage4BError, Stage4BErrorCode

PDBTM_HOST = "pdbtm.unitmp.org"
PDBTM_PORT = 443
PDBTM_ORIGIN = f"https://{PDBTM_HOST}"
PDBTM_USER_AGENT = "MembraneVisualQC/0.5.0.dev0 (+https://github.com/TrPavel/membrane-visual-qc)"
PDBTM_ROLES = ("pdbtm_json", "transformed_pdb")

_RECORD_ID = re.compile(r"^[0-9][A-Za-z0-9]{3}$", flags=re.ASCII)
_MAX_SAFE_HEADER_LENGTH = 1024


class CancellationProbe(Protocol):
    """Small transport-facing cancellation protocol."""

    def is_cancelled(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class TransportPolicy:
    """Reviewed Stage 4B1 resource and deadline policy."""

    connect_timeout: float = 5.0
    read_timeout: float = 15.0
    response_timeout: float = 30.0
    read_chunk_bytes: int = 64 * 1024
    max_response_bytes: int = 5 * 1024 * 1024

    def __post_init__(self) -> None:
        numeric = (self.connect_timeout, self.read_timeout, self.response_timeout)
        if any(value <= 0 for value in numeric):
            raise ValueError("Transport deadlines must be positive.")
        if self.read_chunk_bytes <= 0 or self.max_response_bytes <= 0:
            raise ValueError("Transport byte limits must be positive.")


@dataclass(frozen=True, slots=True)
class TransportEvidence:
    """Allowlisted acquisition facts retained alongside exact raw bytes."""

    requested_url: str
    final_url: str
    role: str
    status: int
    content_type: str
    charset: str | None
    content_encoding: str | None
    etag: str | None
    last_modified: str | None
    requested_at: str
    completed_at: str
    byte_size: int
    sha256: str
    tls_verified: bool


@dataclass(frozen=True, slots=True)
class TransportResult:
    """One exact provider payload and its bounded transport evidence."""

    record_id: str
    role: str
    body: bytes
    evidence: TransportEvidence

    @property
    def byte_size(self) -> int:
        """Return the verified raw-body size for provider protocol compatibility."""

        return self.evidence.byte_size

    @property
    def sha256(self) -> str:
        """Return the verified raw-body digest for provider protocol compatibility."""

        return self.evidence.sha256


def canonicalize_pdbtm_record_id(record_id: str) -> str:
    """Validate one legacy PDB identifier and return its lowercase form."""

    if type(record_id) is not str or _RECORD_ID.fullmatch(record_id) is None:
        raise Stage4BError(Stage4BErrorCode.INVALID_RECORD_ID)
    return record_id.lower()


def _path_for(record_id: str, role: str) -> str:
    if role == "pdbtm_json":
        suffix = "json"
    elif role == "transformed_pdb":
        suffix = "trpdb"
    else:
        raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
    return f"/api/v1/entry/{record_id}.{suffix}"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _cancelled(cancellation: CancellationProbe | None) -> bool:
    return cancellation is not None and bool(cancellation.is_cancelled())


def _raise_if_cancelled(cancellation: CancellationProbe | None) -> None:
    if _cancelled(cancellation):
        raise Stage4BError(Stage4BErrorCode.RETRIEVAL_CANCELLED)


def _header_values(response: http.client.HTTPResponse, name: str) -> list[str]:
    headers = response.headers
    get_all = getattr(headers, "get_all", None)
    if callable(get_all):
        return list(get_all(name, []))
    return [value for key, value in response.getheaders() if key.lower() == name.lower()]


def _single_header(
    response: http.client.HTTPResponse,
    name: str,
    *,
    required: bool = False,
) -> str | None:
    values = _header_values(response, name)
    if len(values) > 1 or (required and not values):
        raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
    return values[0] if values else None


def _safe_optional_header(response: http.client.HTTPResponse, name: str) -> str | None:
    value = _single_header(response, name)
    if value is None:
        return None
    if len(value) > _MAX_SAFE_HEADER_LENGTH or any(
        ord(character) < 0x20 or ord(character) > 0x7E for character in value
    ):
        raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
    return value


def _parse_content_type(value: str, role: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in value.split(";")]
    media_type = parts[0].lower()
    parameters: dict[str, str] = {}
    for part in parts[1:]:
        if not part or "=" not in part:
            raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
        name, parameter_value = (item.strip() for item in part.split("=", 1))
        name = name.lower()
        if name in parameters or name != "charset":
            raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
        if len(parameter_value) >= 2 and parameter_value[0] == parameter_value[-1] == '"':
            parameter_value = parameter_value[1:-1]
        parameters[name] = parameter_value.lower()

    charset = parameters.get("charset")
    if charset is not None and charset not in {"utf-8", "utf8"}:
        raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
    if media_type == "text/plain":
        if charset is None:
            raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
    elif media_type == "application/json":
        if role != "pdbtm_json":
            raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
    else:
        raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
    return media_type, "utf-8" if charset is not None else None


def _map_status(status: int) -> None:
    if status == 200:
        return
    if 300 <= status <= 399:
        raise Stage4BError(Stage4BErrorCode.REDIRECT_DISALLOWED)
    if status == 407:
        raise Stage4BError(Stage4BErrorCode.PROXY_UNSUPPORTED)
    if status == 404:
        raise Stage4BError(Stage4BErrorCode.PROVIDER_NOT_FOUND)
    if status == 408:
        raise Stage4BError(Stage4BErrorCode.NETWORK_TIMEOUT)
    if status == 429:
        raise Stage4BError(Stage4BErrorCode.PROVIDER_RATE_LIMITED)
    if 500 <= status <= 599:
        raise Stage4BError(Stage4BErrorCode.PROVIDER_SERVER_ERROR)
    raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)


class PdbtmHttpsTransport:
    """Perform one direct HTTPS GET against a fixed reviewed PDBTM endpoint."""

    def __init__(
        self,
        *,
        policy: TransportPolicy | None = None,
        connection_factory: Callable[..., http.client.HTTPSConnection] | None = None,
        ssl_context_factory: Callable[[], ssl.SSLContext] = ssl.create_default_context,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] | None = None,
    ) -> None:
        self.policy = policy or TransportPolicy()
        self._connection_factory = connection_factory or http.client.HTTPSConnection
        self._ssl_context_factory = ssl_context_factory
        self._monotonic = monotonic
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))

    def fetch(
        self,
        record_id: str,
        role: str,
        *,
        cancellation: CancellationProbe | None = None,
        pair_deadline: float | None = None,
    ) -> TransportResult:
        """Fetch one role without redirects, retries, proxies, or decompression."""

        canonical_id = canonicalize_pdbtm_record_id(record_id)
        path = _path_for(canonical_id, role)
        requested_url = f"{PDBTM_ORIGIN}{path}"
        started = self._monotonic()
        response_deadline = started + self.policy.response_timeout
        deadline = (
            min(response_deadline, pair_deadline)
            if pair_deadline is not None
            else response_deadline
        )
        requested_at = _format_utc(self._utc_now())
        _raise_if_cancelled(cancellation)
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise Stage4BError(Stage4BErrorCode.NETWORK_TIMEOUT)

        connection: http.client.HTTPSConnection | None = None
        try:
            context = self._ssl_context_factory()
            if context.check_hostname is not True or context.verify_mode != ssl.CERT_REQUIRED:
                raise Stage4BError(Stage4BErrorCode.TLS_ERROR)
            connection = self._connection_factory(
                PDBTM_HOST,
                PDBTM_PORT,
                timeout=min(self.policy.connect_timeout, remaining),
                context=context,
            )
            connection.connect()
            # Capture the connected socket now, once. http.client.HTTPConnection
            # always sends Connection: close (below), and CPython's own
            # getresponse() nulls connection.sock and hands the still-live
            # socket to the response the moment it parses a will-close
            # response -- before the body is ever read. Re-reading
            # connection.sock after that point is unreliable; the captured
            # reference below is the single source of truth for the rest of
            # this fetch.
            sock = connection.sock
            if sock is None:
                raise Stage4BError(Stage4BErrorCode.NETWORK_UNAVAILABLE)
            _raise_if_cancelled(cancellation)
            self._set_read_timeout(sock, deadline)
            connection.request(
                "GET",
                path,
                body=None,
                headers={
                    "Host": PDBTM_HOST,
                    "Accept": "application/json, text/plain"
                    if role == "pdbtm_json"
                    else "text/plain",
                    "Accept-Encoding": "identity",
                    "User-Agent": PDBTM_USER_AGENT,
                    "Connection": "close",
                },
            )
            _raise_if_cancelled(cancellation)
            self._set_read_timeout(sock, deadline)
            response = connection.getresponse()
            _raise_if_cancelled(cancellation)
            self._check_deadline(deadline)
            _map_status(response.status)

            content_type_value = _single_header(response, "Content-Type", required=True)
            assert content_type_value is not None
            content_type, charset = _parse_content_type(content_type_value, role)
            content_encoding = _single_header(response, "Content-Encoding")
            if content_encoding is not None:
                if content_encoding.strip().lower() != "identity":
                    raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
                content_encoding = "identity"

            transfer_encoding = _single_header(response, "Transfer-Encoding")
            content_length = _single_header(response, "Content-Length")
            if transfer_encoding is not None:
                if transfer_encoding.strip().lower() != "chunked" or content_length is not None:
                    raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
            declared_size: int | None = None
            if content_length is not None:
                if not content_length.isascii() or not content_length.isdigit():
                    raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
                declared_size = int(content_length)
                if declared_size > self.policy.max_response_bytes:
                    raise Stage4BError(Stage4BErrorCode.RESPONSE_TOO_LARGE)

            etag = _safe_optional_header(response, "ETag")
            last_modified = _safe_optional_header(response, "Last-Modified")
            body = self._read_body(sock, response, deadline, cancellation)
            if declared_size is not None and len(body) != declared_size:
                raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID)
            completed_at = _format_utc(self._utc_now())
            evidence = TransportEvidence(
                requested_url=requested_url,
                final_url=requested_url,
                role=role,
                status=200,
                content_type=content_type,
                charset=charset,
                content_encoding=content_encoding,
                etag=etag,
                last_modified=last_modified,
                requested_at=requested_at,
                completed_at=completed_at,
                byte_size=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                tls_verified=True,
            )
            return TransportResult(canonical_id, role, body, evidence)
        except Stage4BError:
            raise
        except ssl.SSLError as error:
            if _cancelled(cancellation):
                raise Stage4BError(Stage4BErrorCode.RETRIEVAL_CANCELLED) from error
            raise Stage4BError(Stage4BErrorCode.TLS_ERROR) from error
        except (TimeoutError, socket.timeout) as error:
            if _cancelled(cancellation):
                raise Stage4BError(Stage4BErrorCode.RETRIEVAL_CANCELLED) from error
            raise Stage4BError(Stage4BErrorCode.NETWORK_TIMEOUT) from error
        except (http.client.HTTPException, OSError) as error:
            if _cancelled(cancellation):
                raise Stage4BError(Stage4BErrorCode.RETRIEVAL_CANCELLED) from error
            if isinstance(error, (http.client.BadStatusLine, http.client.IncompleteRead)):
                raise Stage4BError(Stage4BErrorCode.PROVIDER_RESPONSE_INVALID) from error
            raise Stage4BError(Stage4BErrorCode.NETWORK_UNAVAILABLE) from error
        finally:
            if connection is not None:
                try:
                    connection.close()
                except (OSError, http.client.HTTPException):
                    pass

    def _set_read_timeout(self, sock: ssl.SSLSocket, deadline: float) -> None:
        self._check_deadline(deadline)
        remaining = deadline - self._monotonic()
        sock.settimeout(min(self.policy.read_timeout, remaining))

    def _check_deadline(self, deadline: float) -> None:
        if self._monotonic() >= deadline:
            raise Stage4BError(Stage4BErrorCode.NETWORK_TIMEOUT)

    def _read_body(
        self,
        sock: ssl.SSLSocket,
        response: http.client.HTTPResponse,
        deadline: float,
        cancellation: CancellationProbe | None,
    ) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            _raise_if_cancelled(cancellation)
            if response.isclosed():
                # The body has already been fully delivered (http.client
                # detected the final chunk/declared length during the
                # previous read). Re-arming a timeout on the captured socket
                # here is both unnecessary and unsafe: once will-close
                # ownership has been transferred and the body fully drained,
                # the socket is no longer guaranteed usable.
                break
            self._set_read_timeout(sock, deadline)
            chunk = response.read(self.policy.read_chunk_bytes)
            _raise_if_cancelled(cancellation)
            self._check_deadline(deadline)
            if not chunk:
                break
            total += len(chunk)
            if total > self.policy.max_response_bytes:
                raise Stage4BError(Stage4BErrorCode.RESPONSE_TOO_LARGE)
            chunks.append(chunk)
        return b"".join(chunks)
