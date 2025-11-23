"""Base client for OPNsense API communication."""

import json
import logging
from typing import Any
from urllib.parse import urljoin

import httpx

from opnsense_api.openapi import APIWrapper
from opnsense_api.specs import find_best_matching_spec

logger = logging.getLogger(__name__)


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
        spec_version: str | None = None,
        auto_detect_version: bool = True,
    ) -> None:
        """Initialize OPNsense API client.

        Args:
            base_url: Base URL of OPNsense instance (e.g., "https://opnsense.local")
            api_key: API key for authentication
            api_secret: API secret for authentication
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
            spec_version: Specific OpenAPI spec version to use (e.g., '24.7.1').
                         If None, will auto-detect from server.
            auto_detect_version: If True and spec_version is None, automatically
                                detect version from server
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

        # OpenAPI wrapper (lazily initialized)
        self._openapi: APIWrapper | None = None
        self._detected_version: str | None = None
        self._spec_version = spec_version

        # Auto-detect version if requested
        if auto_detect_version and spec_version is None:
            try:
                self._detected_version = self.detect_version()
                logger.info(f"Detected OPNsense version: {self._detected_version}")
            except Exception as e:
                logger.warning(f"Could not auto-detect version: {e}. OpenAPI features disabled.")
                self._detected_version = None

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
            raise APIResponseError(f"Invalid JSON response from {url}: {e}", response.text) from e

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
            raise APIResponseError(f"Invalid JSON response from {url}: {e}", response.text) from e

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "OPNsenseClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def detect_version(self) -> str:
        """Detect OPNsense version from the server.

        Returns:
            Version string (e.g., '24.7.1')

        Raises:
            APIResponseError: If version cannot be retrieved
            KeyError: If response doesn't contain expected version field
        """
        try:
            # Try to get version from core/firmware/status
            response = self.get("core", "firmware", "status")

            # Response typically has 'product_version' field
            if "product_version" in response:
                version = response["product_version"]
                logger.debug(f"Got version from firmware status: {version}")
                return version

            # Fallback: try diagnostics/system/systemInformation
            response = self.get("diagnostics", "system", "systemInformation")
            if "versions" in response and "product_version" in response["versions"]:
                version = response["versions"]["product_version"]
                logger.debug(f"Got version from system information: {version}")
                return version

            raise KeyError("Version field not found in API response")
        except Exception as e:
            logger.error(f"Failed to detect version: {e}")
            raise

    @property
    def openapi(self) -> APIWrapper:
        """Get the OpenAPI wrapper instance.

        Lazily initializes the wrapper with the appropriate spec file.

        Returns:
            APIWrapper instance

        Raises:
            RuntimeError: If no version is available (neither specified nor detected)
            FileNotFoundError: If spec file for the version doesn't exist
        """
        if self._openapi is None:
            # Determine which version to use
            version = self._spec_version or self._detected_version

            if version is None:
                raise RuntimeError(
                    "No OPNsense version available. Either specify spec_version "
                    "or enable auto_detect_version."
                )

            # Find the best matching spec file
            spec_path = find_best_matching_spec(version)
            logger.info(f"Loading OpenAPI spec from: {spec_path}")

            # Initialize APIWrapper
            self._openapi = APIWrapper(
                api_json_file=str(spec_path),
                base_url=self.base_url,
                api_key=self.api_key,
                api_secret=self.api_secret,
                timeout=self.timeout,
                session=None,  # Let APIWrapper create its own client
                verify_ssl=self.verify_ssl,
            )

        return self._openapi

    def list_endpoints(self) -> list[tuple[str, str, str | None]]:
        """List all available API endpoints from the OpenAPI spec.

        Returns:
            List of (path, METHOD, summary) tuples

        Raises:
            RuntimeError: If OpenAPI wrapper is not available
        """
        return self.openapi.list_endpoints()

    def get_endpoint_info(self, path_template: str, method: str = "GET") -> dict[str, Any]:
        """Get detailed information about an API endpoint.

        Args:
            path_template: API path template (e.g., '/firewall/alias/{uuid}')
            method: HTTP method (default: 'GET')

        Returns:
            Dictionary with path_params, query_params, headers, body_sample, and summary

        Raises:
            RuntimeError: If OpenAPI wrapper is not available
            KeyError: If endpoint not found in spec
        """
        return self.openapi.suggest_parameters(path_template, method)
