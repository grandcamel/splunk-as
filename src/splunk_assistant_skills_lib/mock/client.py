"""
Full Mock Splunk Client

Combines all mixins to provide a complete mock implementation
of the SplunkClient for comprehensive testing.
"""

from typing import Any

from .base import MockSplunkClientBase
from .mixins.admin import AdminMixin
from .mixins.job import JobMixin
from .mixins.metadata import MetadataMixin
from .mixins.search import SearchMixin


class MockSplunkClient(
    SearchMixin, JobMixin, MetadataMixin, AdminMixin, MockSplunkClientBase
):
    """Full mock Splunk client with all mixins.

    Provides complete mock functionality for testing all skill areas:
    - Search operations (oneshot, normal, blocking)
    - Job lifecycle management
    - Metadata discovery
    - Administrative operations

    Example:
        >>> client = MockSplunkClient()
        >>> # Test search
        >>> result = client.oneshot_search("index=main | head 10")
        >>> assert len(result["results"]) > 0
        >>> # Verify API calls
        >>> client.assert_called("POST", "/search/jobs/oneshot")

    For partial mocking, create a custom class with specific mixins:
        >>> class SearchOnlyMock(SearchMixin, MockSplunkClientBase):
        ...     pass
        >>> client = SearchOnlyMock()
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the full mock client.

        Accepts the same parameters as SplunkClient for compatibility.
        """
        super().__init__(*args, **kwargs)

    def reset(self) -> None:
        """Reset all mock state.

        Clears:
        - Recorded API calls
        - Response overrides
        - Error simulations
        - Job state
        - Search results
        """
        self.clear_calls()
        self.clear_overrides()
        self.clear_jobs()
        self._search_results.clear()
        self._oneshot_results.clear()

    def __repr__(self) -> str:
        return f"MockSplunkClient(base_url={self.base_url!r})"


# Convenience factory functions


def create_mock_client(**kwargs: Any) -> MockSplunkClient:
    """Create a MockSplunkClient with default settings.

    Args:
        **kwargs: Override default settings

    Returns:
        Configured MockSplunkClient
    """
    defaults = {
        "base_url": "https://mock-splunk.example.com",
        "token": "mock-token",
        "port": 8089,
    }
    defaults.update(kwargs)
    return MockSplunkClient(**defaults)


def create_cloud_mock(**kwargs: Any) -> MockSplunkClient:
    """Create a MockSplunkClient configured as Splunk Cloud.

    Args:
        **kwargs: Override default settings

    Returns:
        Cloud-configured MockSplunkClient
    """
    defaults = {
        "base_url": "https://acme.splunkcloud.com",
        "token": "mock-cloud-token",
        "port": 8089,
    }
    defaults.update(kwargs)
    return MockSplunkClient(**defaults)
