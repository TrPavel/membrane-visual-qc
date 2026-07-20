"""Global test safety gates.

Normal tests may use loopback sockets, but must never contact a provider or any
other non-local network endpoint.
"""

from __future__ import annotations

import ipaddress
import socket

import pytest


def _loopback_destination(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return True
    host = address[0]
    if not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def install_non_loopback_socket_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deny non-loopback INET connections without resolving hostnames."""

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def guarded_connect(sock: socket.socket, address: object) -> object:
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not _loopback_destination(address):
            raise AssertionError("Normal tests attempted a non-loopback network connection.")
        return original_connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: object) -> int:
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not _loopback_destination(address):
            raise AssertionError("Normal tests attempted a non-loopback network connection.")
        return original_connect_ex(sock, address)

    def guarded_create_connection(
        address: object, *args: object, **kwargs: object
    ) -> socket.socket:
        if not _loopback_destination(address):
            raise AssertionError("Normal tests attempted a non-loopback network connection.")
        return original_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)


@pytest.fixture(autouse=True)
def _deny_non_loopback_network(monkeypatch: pytest.MonkeyPatch) -> None:
    install_non_loopback_socket_guard(monkeypatch)
