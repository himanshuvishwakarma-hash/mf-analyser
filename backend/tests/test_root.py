"""Sanity tests that don't require a live database."""
from __future__ import annotations


def test_root_returns_service_info(client) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "mf-analyser"
    assert body["docs"] == "/docs"


def test_docs_endpoint_available(client) -> None:
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_openapi_schema(client) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "Z1N Capital - MF Analyser API"
