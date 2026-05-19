"""MFApi.in async client.

API reference (public, per spec section 10.1):

    GET /mf
        -> list[ { "schemeCode": int, "schemeName": str } ]

    GET /mf/{scheme_code}
        -> {
            "meta": {
                "fund_house": str,
                "scheme_type": str,
                "scheme_category": str,
                "scheme_code": int,
                "scheme_name": str,
                "isin_growth": str | null,
                "isin_div_reinvestment": str | null
            },
            "data": [ { "date": "DD-MM-YYYY", "nav": "123.4567" }, ... ],
            "status": "SUCCESS"
        }

    GET /mf/{scheme_code}/latest
        -> same envelope as above with `data` truncated to the most recent NAV.

    GET /mf/search?q=<query>
        -> list[ { "schemeCode": int, "schemeName": str } ]

The endpoint shapes are tracked in tests/test_data_fetch fixtures. If
MFApi.in changes its contract, update both the fixtures and the parsers
in app/services/ingestion.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)


class MFApiError(RuntimeError):
    """Raised when MFApi.in returns an unexpected response."""


class MFApiClient:
    """Async client for https://api.mfapi.in.

    Designed for batch use from Celery tasks. Respects the 100ms request
    spacing recommended by spec section 10.1 and retries transient failures
    with exponential backoff.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        request_delay_ms: int | None = None,
        max_attempts: int = 4,
    ) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.mfapi_base_url
        self._delay = (request_delay_ms or settings.mfapi_request_delay_ms) / 1000.0
        self._max_attempts = max_attempts
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, trust_env=False)

    async def __aenter__(self) -> MFApiClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> Any:
        """Internal GET with retry, rate-limit pause, and structured logging."""
        await asyncio.sleep(self._delay)
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_attempts),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
                reraise=True,
            ):
                with attempt:
                    resp = await self._client.get(path)
                    resp.raise_for_status()
                    return resp.json()
        except RetryError as e:  # pragma: no cover - defensive
            raise MFApiError(f"MFApi {path} failed after {self._max_attempts} attempts") from e

    async def list_all_funds(self) -> list[dict[str, Any]]:
        """Full AMFI fund master.

        Returns approximately 2,100 records of {schemeCode, schemeName}. Used
        by the nightly refresh_fund_master task to detect new and retired
        schemes.
        """
        data = await self._get("/mf")
        if not isinstance(data, list):
            raise MFApiError(f"/mf expected list, got {type(data).__name__}")
        return data

    async def get_fund(self, scheme_code: int) -> dict[str, Any]:
        """Full fund detail plus complete NAV history."""
        data = await self._get(f"/mf/{scheme_code}")
        if not isinstance(data, dict) or "meta" not in data or "data" not in data:
            raise MFApiError(f"/mf/{scheme_code} returned unexpected shape")
        return data

    async def get_latest_nav(self, scheme_code: int) -> dict[str, Any]:
        """Same envelope as get_fund but data is a single most-recent NAV."""
        data = await self._get(f"/mf/{scheme_code}/latest")
        if not isinstance(data, dict) or "data" not in data:
            raise MFApiError(f"/mf/{scheme_code}/latest returned unexpected shape")
        return data

    async def search(self, query: str) -> list[dict[str, Any]]:
        """Server-side name search (used as a fallback when DB is empty)."""
        data = await self._get(f"/mf/search?q={query}")
        if not isinstance(data, list):
            raise MFApiError("/mf/search expected list")
        return data
