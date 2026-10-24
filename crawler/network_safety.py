#!/usr/bin/env python3
"""Validation des destinations réseau pour KSEARCHBOT."""

import ipaddress
import socket
from urllib.parse import urlsplit


def validate_url(url):
    parsed = urlsplit(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Protocole interdit")

    if parsed.username or parsed.password:
        raise ValueError("Identifiants dans l'URL interdits")

    if parsed.port not in (None, 80, 443):
        raise ValueError("Port interdit")

    host = (parsed.hostname or "").lower().rstrip(".")

    if not host or host == "localhost" or host.endswith(".local"):
        raise ValueError("Hôte local interdit")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None and not ip.is_global:
        raise ValueError("Adresse IP non publique")

    addresses = socket.getaddrinfo(
        host,
        None,
        type=socket.SOCK_STREAM
    )

    if not addresses:
        raise ValueError("Aucune adresse DNS")

    for item in addresses:
        address = ipaddress.ip_address(item[4][0])

        if not address.is_global:
            raise ValueError(
                "Résolution DNS vers une adresse non publique"
            )

    return host


if __name__ == "__main__":
    blocked = [
        "http://127.0.0.1/",
        "http://192.168.1.1/",
        "http://10.0.0.1/",
        "http://localhost/",
        "file:///etc/passwd",
        "http://user:pass@example.com/",
        "http://example.com:8080/",
    ]

    for url in blocked:
        try:
            validate_url(url)
        except ValueError:
            print("BLOQUÉ :", url)
        else:
            raise AssertionError(
                "URL dangereuse acceptée : " + url
            )

    print("=== KSEARCHBOT SÉCURITÉ RÉSEAU ===")
    print("Tests des destinations interdites : OK")
