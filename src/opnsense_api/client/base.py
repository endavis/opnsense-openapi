"""Base client for OPNsense API communication."""

import json
from typing import Any
from urllib.parse import urljoin

import httpx


class APIResponseError(Exception):
    """Raised when API response cannot be parsed as JSON."""

    def __init__(self, message: str, response_text: str) -> None:
        super().__init__(message)
        self.response_text = response_text


class OPNsenseClient:
    """Base HTTP client for OPNsense API with key/secret authentication.

    The OPNsense API uses API key and secret for authentication via HTTP Basic Auth.
    All requests return JSON and most operations use GET (retrieve) or POST (modify).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_secret: str,
        verify_ssl: bool = True,
        timeout: float = 30.0,
    ) -> None:
        """Initialize OPNsense API client.

        Args:
            base_url: Base URL of OPNsense instance (e.g., "https://opnsense.local")
            api_key: API key for authentication
            api_secret: API secret for authentication
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        self._client = httpx.Client(
            auth=(api_key, api_secret),
            verify=verify_ssl,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    def _build_url(self, module: str, controller: str, command: str, *params: str) -> str:
        """Build API endpoint URL.

        Args:
            module: API module name (e.g., "firewall")
            controller: Controller name (e.g., "alias_util")
            command: Command/action name (e.g., "findAlias")
            *params: Additional URL parameters

        Returns:
            Complete API endpoint URL
        """
        parts = ["api", module, controller, command]
        parts.extend(params)
        path = "/".join(parts)
        return urljoin(f"{self.base_url}/", path)

    def get(
        self, module: str, controller: str, command: str, *params: str, **query: Any
    ) -> dict[str, Any]:
        """Execute GET request to API endpoint.

        Args:
            module: API module name
            controller: Controller name
            command: Command/action name
            *params: URL path parameters
            **query: Query string parameters

        Returns:
            JSON response as dictionary

        Raises:
            httpx.HTTPError: On HTTP errors
            APIResponseError: If response is not valid JSON
        """
        url = self._build_url(module, controller, command, *params)
        response = self._client.get(url, params=query)
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise APIResponseError(
                f"Invalid JSON response from {url}: {e}", response.text
            ) from e

    def post(
        self,
        module: str,
        controller: str,
        command: str,
        *params: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute POST request to API endpoint.

        Args:
            module: API module name
            controller: Controller name
            command: Command/action name
            *params: URL path parameters
            json: JSON request body

        Returns:
            JSON response as dictionary

        Raises:
            httpx.HTTPError: On HTTP errors
            APIResponseError: If response is not valid JSON
        """
        url = self._build_url(module, controller, command, *params)
        response = self._client.post(url, json=json)
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise APIResponseError(
                f"Invalid JSON response from {url}: {e}", response.text
            ) from e

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "OPNsenseClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()
