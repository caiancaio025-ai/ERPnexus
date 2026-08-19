from starlette.requests import Request

from app.auth.rate_limit import _client_ip, _hash_key


def _request(*, client: tuple[str, int], forwarded_for: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": headers,
            "client": client,
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_rate_limit_hash_normalizes_identifier() -> None:
    assert _hash_key("identifier", " Admin@Example.com ") == _hash_key(
        "identifier",
        "admin@example.com",
    )


def test_rate_limit_hash_separates_scopes() -> None:
    value = "192.0.2.15"
    assert _hash_key("ip", value) != _hash_key("identifier", value)


def test_client_ip_uses_direct_client_without_proxy_header() -> None:
    request = _request(client=("127.0.0.1", 12345))
    assert _client_ip(request) == "127.0.0.1"


def test_client_ip_uses_last_forwarded_hop() -> None:
    request = _request(
        client=("172.18.0.4", 12345),
        forwarded_for="203.0.113.10, 198.51.100.20",
    )
    assert _client_ip(request) == "198.51.100.20"
