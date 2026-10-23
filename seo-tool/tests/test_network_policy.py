import socket

from seo_tool.config import Config
from seo_tool.http import FetchResult, Fetcher
from seo_tool.urls import network_policy_error


def test_network_policy_blocks_local_and_metadata_hosts():
    assert "local or cloud-metadata" in network_policy_error("http://localhost:8080/")
    assert "cloud-metadata" in network_policy_error("http://metadata.google.internal/")
    assert "non-public" in network_policy_error("http://169.254.169.254/latest/meta-data/")


def test_network_policy_blocks_private_dns_results(monkeypatch):
    def private_record(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.10.0.8", 443))]

    monkeypatch.setattr("seo_tool.urls.socket.getaddrinfo", private_record)
    assert "non-public address (10.10.0.8)" in network_policy_error("https://example.test/")


def test_network_policy_allows_public_dns_results(monkeypatch):
    def public_record(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr("seo_tool.urls.socket.getaddrinfo", public_record)
    assert network_policy_error("https://example.test/") is None
    assert network_policy_error("http://127.0.0.1/", allow_private_networks=True) is None


def test_fetcher_rejects_private_targets_before_robots(monkeypatch):
    fetcher = Fetcher(Config())
    try:
        monkeypatch.setattr(fetcher, "allowed", lambda _url: (_ for _ in ()).throw(AssertionError("robots called")))
        result = fetcher.fetch("http://127.0.0.1:8080/")
    finally:
        fetcher.close()

    assert result.blocked_by_network_policy
    assert result.status is None


def test_fetcher_rechecks_network_policy_on_redirect(monkeypatch):
    fetcher = Fetcher(Config())
    calls = []

    def policy(url, _allow_private):
        return "blocked by network policy: non-public address" if "169.254.169.254" in url else None

    def request(url, *_args, **_kwargs):
        calls.append(url)
        return FetchResult(url=url, final_url=url, status=302, headers={"location": "http://169.254.169.254/"})

    try:
        monkeypatch.setattr("seo_tool.http.network_policy_error", policy)
        monkeypatch.setattr(fetcher, "allowed", lambda _url: True)
        monkeypatch.setattr(fetcher, "_delay", lambda _url: 0.0)
        monkeypatch.setattr(fetcher, "_request", request)
        result = fetcher.fetch("https://example.com/")
    finally:
        fetcher.close()

    assert calls == ["https://example.com/"]
    assert result.blocked_by_network_policy
    assert result.final_url == "http://169.254.169.254/"
