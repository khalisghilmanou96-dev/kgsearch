#!/usr/bin/env python3
"""Session HTTP KSEARCHBOT avec contrôle DNS à la connexion."""

import ipaddress
import socket

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager

from network_safety import validate_url


def guarded_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                              source_address=None, socket_options=None):
    host, port = address

    candidates = socket.getaddrinfo(
        host, port, type=socket.SOCK_STREAM
    )

    if not candidates:
        raise OSError("Aucune adresse DNS")

    for family, socktype, proto, canonname, sockaddr in candidates:
        ip = ipaddress.ip_address(sockaddr[0])

        if not ip.is_global:
            raise OSError(
                "Connexion vers une adresse non publique interdite"
            )

    last_error = None

    for family, socktype, proto, canonname, sockaddr in candidates:
        sock = None

        try:
            sock = socket.socket(family, socktype, proto)

            if socket_options:
                for option in socket_options:
                    sock.setsockopt(*option)

            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)

            if source_address:
                sock.bind(source_address)

            sock.connect(sockaddr)
            return sock

        except OSError as exc:
            last_error = exc

            if sock is not None:
                sock.close()

    raise last_error or OSError("Connexion impossible")


class GuardedHTTPConnection(HTTPConnection):
    def _new_conn(self):
        try:
            return guarded_create_connection(
                (self._dns_host, self.port),
                self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except OSError as exc:
            raise urllib3.exceptions.NewConnectionError(
                self, f"Connexion refusée : {exc}"
            ) from exc


class GuardedHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        try:
            return guarded_create_connection(
                (self._dns_host, self.port),
                self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except OSError as exc:
            raise urllib3.exceptions.NewConnectionError(
                self, f"Connexion refusée : {exc}"
            ) from exc


class GuardedHTTPPool(HTTPConnectionPool):
    ConnectionCls = GuardedHTTPConnection


class GuardedHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = GuardedHTTPSConnection


class SafeHTTPAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False,
                         **pool_kwargs):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs,
        )

        self.poolmanager.pool_classes_by_scheme = {
            "http": GuardedHTTPPool,
            "https": GuardedHTTPSPool,
        }

    def send(self, request, **kwargs):
        validate_url(request.url)
        return super().send(request, **kwargs)


def create_session():
    session = requests.Session()
    session.trust_env = False

    adapter = SafeHTTPAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


if __name__ == "__main__":
    from unittest.mock import patch

    private_result = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("127.0.0.1", 443),
        )
    ]

    with patch("socket.getaddrinfo", return_value=private_result):
        try:
            guarded_create_connection(("example.com", 443))
        except OSError:
            print("IP privée bloquée à la connexion : OK")
        else:
            raise AssertionError("IP privée acceptée")

    session = create_session()

    assert session.trust_env is False

    print("Session HTTP sécurisée : OK")
    print("Aucune connexion Internet lancée")
