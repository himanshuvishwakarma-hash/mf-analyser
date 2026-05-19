"""Tests for MFApiClient shape validation. Network is mocked via httpx_mock-style
stubs: we monkeypatch the internal _get method directly to skip httpx entirely.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core.data_fetch import MFApiClient, MFApiError


def _run(coro):
    return asyncio.run(coro)


def test_list_all_funds_rejects_non_list(monkeypatch) -> None:
    async def stub_get(self, path):
        return {"not": "a list"}

    monkeypatch.setattr(MFApiClient, "_get", stub_get)

    async def run():
        async with MFApiClient() as c:
            with pytest.raises(MFApiError):
                await c.list_all_funds()

    _run(run())


def test_get_fund_rejects_missing_meta(monkeypatch) -> None:
    async def stub_get(self, path):
        return {"data": []}  # missing 'meta'

    monkeypatch.setattr(MFApiClient, "_get", stub_get)

    async def run():
        async with MFApiClient() as c:
            with pytest.raises(MFApiError):
                await c.get_fund(123)

    _run(run())


def test_get_latest_nav_rejects_missing_data(monkeypatch) -> None:
    async def stub_get(self, path):
        return {"meta": {}}  # missing 'data'

    monkeypatch.setattr(MFApiClient, "_get", stub_get)

    async def run():
        async with MFApiClient() as c:
            with pytest.raises(MFApiError):
                await c.get_latest_nav(123)

    _run(run())


def test_search_rejects_non_list(monkeypatch) -> None:
    async def stub_get(self, path):
        return {"not": "list"}

    monkeypatch.setattr(MFApiClient, "_get", stub_get)

    async def run():
        async with MFApiClient() as c:
            with pytest.raises(MFApiError):
                await c.search("axis")

    _run(run())


def test_get_fund_happy_path(monkeypatch) -> None:
    async def stub_get(self, path):
        return {"meta": {"fund_house": "Axis"}, "data": [{"date": "01-01-2024", "nav": "10"}]}

    monkeypatch.setattr(MFApiClient, "_get", stub_get)

    async def run():
        async with MFApiClient() as c:
            payload = await c.get_fund(100027)
            assert payload["meta"]["fund_house"] == "Axis"
            assert len(payload["data"]) == 1

    _run(run())
