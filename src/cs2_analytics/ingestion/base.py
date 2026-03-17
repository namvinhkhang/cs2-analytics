"""Abstract base class for all CS2 data API ingestion clients.

Provides shared retry logic (tenacity), rate-limiting (asyncio.Semaphore),
structured logging (structlog), and async context manager lifecycle management.

Subclasses must define:
- BASE_URL: str  — root URL passed to httpx.AsyncClient
- _semaphore: asyncio.Semaphore  — class-level concurrency cap
- _auth_headers()  — authentication headers dict
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

# Module-level structured logger — emits JSON-compatible log events
logger = structlog.get_logger()


class BaseAPIClient(ABC):
    """Abstract base for all CS2 data API clients.

    Subclasses must define:
        BASE_URL: str  — base URL passed to httpx.AsyncClient
        _semaphore: asyncio.Semaphore  — concurrency limit (class-level)
        _auth_headers() -> dict[str, str]  — authentication headers

    The class-level _semaphore is intentional: all instances of a concrete
    subclass share one semaphore, which enforces global rate limiting for
    that API source even when multiple client instances exist.
    """

    BASE_URL: str
    # Subclasses override this with the appropriate concurrency cap (e.g., Semaphore(1))
    _semaphore: asyncio.Semaphore

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # Build the httpx async client with auth headers baked in at construction
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._auth_headers(),
            timeout=30.0,
            # Prevent respx mocks from following redirect URLs to unmocked targets
            follow_redirects=False,
        )

    @abstractmethod
    def _auth_headers(self) -> dict[str, str]:
        """Return authentication headers for this API source."""
        ...

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        # Retry on rate-limit errors (429) and server errors (5xx) and timeouts
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,  # re-raise the last exception after all retries exhausted
    )
    async def get(self, path: str, **params: Any) -> dict[str, Any]:
        """Make a rate-limited GET request with automatic retry on transient errors.

        Acquires the class-level semaphore before each request to enforce
        concurrency limits. Raises HTTPStatusError on 429 explicitly so
        tenacity's retry_if_exception_type can catch and retry it
        (httpx only raises on 4xx after raise_for_status() is called).
        """
        async with self._semaphore:
            response = await self._client.get(path, params=params)
            if response.status_code == 429:
                # Explicitly raise so tenacity retries rather than continuing
                raise httpx.HTTPStatusError(
                    "Rate limited (429)",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    async def paginate(
        self,
        path: str,
        *,
        offset_key: str = "offset",
        limit: int = 100,
        results_key: str = "items",
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Paginate through results, yielding each page as a list.

        Stops when the page returns fewer items than the limit (last page)
        or when the results list is empty.
        """
        offset = 0
        while True:
            data = await self.get(path, **{offset_key: offset, "limit": limit})
            items: list[dict[str, Any]] = data.get(results_key, [])
            if not items:
                break
            yield items
            if len(items) < limit:
                break  # last page reached
            offset += limit

    async def __aenter__(self) -> BaseAPIClient:
        """Return self to support `async with client:` usage."""
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Close the underlying httpx.AsyncClient to release connections."""
        await self._client.aclose()
