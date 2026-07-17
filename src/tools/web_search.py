"""
Web search tool using Tavily or Serper API with URL validation and SSRF protection.
"""
from __future__ import annotations

import ipaddress
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Private IP ranges for SSRF protection
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
]

# Allowed URL schemes
ALLOWED_SCHEMES = {"https"}

# Default blocked domains (can be overridden by env var)
DEFAULT_BLOCKED_DOMAINS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",  # AWS metadata
}


def is_private_ip(ip: str) -> bool:
    """Check if IP address is in private range."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return any(ip_obj in network for network in PRIVATE_IP_RANGES)
    except ValueError:
        return False


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve hostname to IP addresses."""
    import socket
    try:
        return [info[4][0] for info in socket.getaddrinfo(hostname, None)]
    except Exception:
        return []


def is_url_allowed(url: str, allowed_domains: list[str] | None = None, blocked_domains: set[str] | None = None) -> tuple[bool, str | None]:
    """
    Validate URL for SSRF protection.
    
    Returns:
        Tuple of (is_allowed, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "Invalid URL"
    
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"
    
    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"Scheme '{parsed.scheme}' not allowed. Only HTTPS is permitted."
    
    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"
    
    # Check blocked domains
    blocked = blocked_domains or DEFAULT_BLOCKED_DOMAINS
    if hostname.lower() in blocked:
        return False, f"Domain '{hostname}' is blocked"
    
    # Check allowed domains if specified
    if allowed_domains:
        if not any(hostname.lower().endswith(domain.lower()) for domain in allowed_domains):
            return False, f"Domain '{hostname}' not in allowed list"
    
    # Resolve and check for private IPs
    ips = resolve_hostname(hostname)
    for ip in ips:
        if is_private_ip(ip):
            return False, f"URL resolves to private IP address: {ip}"
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r"^https?://\d+\.\d+\.\d+\.\d+",  # Direct IP access
        r"@[^@]+@",  # Multiple @ signs
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, url):
            return False, "Suspicious URL pattern detected"
    
    return True, None


def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """Sanitize search query input."""
    if not query or not isinstance(query, str):
        return ""
    
    # Remove control characters
    sanitized = "".join(ch for ch in query if ch == "\n" or ch == "\t" or ch == "\r" or ord(ch) >= 32)
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()


class WebSearchResult:
    """Single web search result."""
    def __init__(self, title: str, url: str, content: str, source: str = "web", score: float = 0.0):
        self.title = title
        self.url = url
        self.content = content
        self.source = source
        self.score = score
        self.retrieved_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content[:500],
            "source": self.source,
            "score": self.score,
        }


class WebSearchTool:
    """Tool for searching the web via Tavily or Serper with SSRF protection."""

    def __init__(self):
        settings = get_settings()
        self.tavily_api_key = settings.api_keys.tavily_api_key
        self.serper_api_key = settings.api_keys.serper_api_key
        self._tavily_client = None
        self._serper_client = None
        
        # Load allowed/blocked domains from settings
        self.allowed_domains = settings.security.allowed_domains or None
        self.blocked_domains = DEFAULT_BLOCKED_DOMAINS.copy()

    @property
    def tavily_client(self):
        if self._tavily_client is None and self.tavily_api_key:
            try:
                from tavily import TavilyClient
                self._tavily_client = TavilyClient(api_key=self.tavily_api_key)
            except ImportError:
                logger.warning("tavily-python not installed")
        return self._tavily_client

    @property
    def serper_client(self):
        if self._serper_client is None and self.serper_api_key:
            import requests
            self._serper_client = requests.Session()
        return self._serper_client

    def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        """Search web using available APIs (Tavily preferred, fallback to Serper)."""
        # Sanitize query
        sanitized_query = sanitize_search_query(query)
        if not sanitized_query:
            logger.warning("Empty search query after sanitization")
            return []
        
        if self.tavily_client:
            return self._search_tavily(sanitized_query, max_results)
        if self.serper_api_key:
            return self._search_serper(sanitized_query, max_results)
        logger.warning("No web search API configured (TAVILY_API_KEY or SERPER_API_KEY)")
        return []

    def _search_tavily(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        """Search using Tavily API."""
        try:
            response = self.tavily_client.search(
                query=query,
                max_results=max_results,
                include_answer=False,
            )
            results = []
            for r in response.get("results", []):
                url = r.get("url", "")
                # Validate URL before adding to results
                allowed, error = is_url_allowed(url, self.allowed_domains, self.blocked_domains)
                if not allowed:
                    logger.warning(f"Blocked URL from Tavily results: {url} ({error})")
                    continue
                results.append(WebSearchResult(
                    title=r.get("title", ""),
                    url=url,
                    content=r.get("content", ""),
                    source="tavily",
                    score=r.get("score", 0.0),
                ))
            logger.info(f"Tavily search '{query[:50]}' returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []

    def _search_serper(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        """Search using Serper API."""
        try:
            import requests
            response = requests.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": max_results},
                headers={"X-API-KEY": self.serper_api_key},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for r in data.get("organic", []):
                url = r.get("link", "")
                # Validate URL before adding to results
                allowed, error = is_url_allowed(url, self.allowed_domains, self.blocked_domains)
                if not allowed:
                    logger.warning(f"Blocked URL from Serper results: {url} ({error})")
                    continue
                results.append(WebSearchResult(
                    title=r.get("title", ""),
                    url=url,
                    content=r.get("snippet", ""),
                    source="serper",
                    score=1.0 - (results.index(r) * 0.1) if results else 1.0,
                ))
            logger.info(f"Serper search '{query[:50]}' returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Serper search error: {e}")
            return []

    def search_across_sources(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        """Search with deduplication across multiple sources."""
        all_results = self.search(query, max_results=max_results)
        seen_urls = set()
        deduped = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                deduped.append(r)
        return deduped[:max_results]


_web_search_tool: WebSearchTool | None = None


def get_web_search_tool() -> WebSearchTool:
    global _web_search_tool
    if _web_search_tool is None:
        _web_search_tool = WebSearchTool()
    return _web_search_tool
