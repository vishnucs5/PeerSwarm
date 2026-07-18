"""
Tests for the sliding-window rate limiter.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from src.api.rate_limiter import SlidingWindowRateLimiter


@pytest.fixture
def limiter():
    return SlidingWindowRateLimiter(max_requests=5, window_seconds=60)


class TestSlidingWindowRateLimiter:
    def test_allows_within_limit(self, limiter):
        mock_req = MagicMock()
        mock_req.client.host = "1.2.3.4"
        mock_req.headers = {}
        for _ in range(5):
            allowed, remaining, _ = limiter.is_allowed(mock_req)
            assert allowed

    def test_blocks_over_limit(self, limiter):
        mock_req = MagicMock()
        mock_req.client.host = "1.2.3.4"
        mock_req.headers = {}
        for _ in range(5):
            limiter.is_allowed(mock_req)
        allowed, remaining, retry_after = limiter.is_allowed(mock_req)
        assert not allowed
        assert remaining == 0
        assert retry_after > 0

    def test_remaining_decreases(self, limiter):
        mock_req = MagicMock()
        mock_req.client.host = "1.2.3.4"
        mock_req.headers = {}
        _, remaining1, _ = limiter.is_allowed(mock_req)
        assert remaining1 == 4
        _, remaining2, _ = limiter.is_allowed(mock_req)
        assert remaining2 == 3

    def test_different_clients_independent(self, limiter):
        req_a = MagicMock()
        req_a.client.host = "1.1.1.1"
        req_a.headers = {}
        req_b = MagicMock()
        req_b.client.host = "2.2.2.2"
        req_b.headers = {}
        for _ in range(5):
            limiter.is_allowed(req_a)
        assert not limiter.is_allowed(req_a)[0]
        assert limiter.is_allowed(req_b)[0]

    def test_window_expires(self, limiter):
        mock_req = MagicMock()
        mock_req.client.host = "1.2.3.4"
        mock_req.headers = {}
        for _ in range(5):
            limiter.is_allowed(mock_req)
        limiter._clients["1.2.3.4"] = [time.time() - 120]
        allowed, remaining, _ = limiter.is_allowed(mock_req)
        assert allowed
        assert remaining == 4

    def test_forwarded_for_header(self, limiter):
        mock_req = MagicMock()
        mock_req.client = None
        mock_req.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        allowed, _, _ = limiter.is_allowed(mock_req)
        assert allowed
        assert limiter._clients["10.0.0.1"] == [pytest.approx(time.time(), rel=1)]

    def test_unknown_client(self, limiter):
        mock_req = MagicMock()
        mock_req.client = None
        mock_req.headers = {}
        allowed, _, _ = limiter.is_allowed(mock_req)
        assert allowed

    def test_zero_max_requests_blocks_all(self):
        limiter = SlidingWindowRateLimiter(max_requests=0, window_seconds=60)
        mock_req = MagicMock()
        mock_req.client.host = "1.2.3.4"
        mock_req.headers = {}
        allowed, _, _ = limiter.is_allowed(mock_req)
        assert not allowed
