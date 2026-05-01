"""Base client for OPNsense API communication."""

from __future__ import annotations

import contextlib
import json
import logging
import shutil
import subprocess  # nosec B404 - invoked only via shutil.which-validated entry point
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin

import httpx

from opnsense_openapi.openapi import APIWrapper, SuggestedParameters
from opnsense_openapi.specs import (
    find_best_matching_spec,
    list_available_specs,
    version_from_spec_path,
)

logger = logging.getLogger(__name__)


class APIResponseError(Exception):
    """Raised when API response cannot be parsed as JSON."""

    def __init__(self, message: str, response_text: str) -> None:
        super().__init__(message)
        self.response_text = response_text


def _resolved_module_dir(version: str) -> tuple[Path, str, Path]:
    """Resolve the spec for ``version`` and return its canonical client paths.

    Both ``_auto_generate_client`` and the :pyattr:`OPNsenseClient.api`
    property need the *same* derivation: resolve the spec, then key the
    generated-client directory off the spec's version (not the raw user
    input). Centralizing here keeps them in lock-step and ensures that a
    raw input like ``26.1.6_2`` lands in ``generated/v26_1_6/`` whenever the
    resolver maps it to ``opnsense-26.1.6.json``.

    Args:
        version: Raw OPNsense version string (may include a ``_N`` suffix).

    Returns:
        Tuple of ``(spec_path, resolved_version, client_dir)`` where
        ``resolved_version`` is the version segment of ``spec_path`` (e.g.
        ``"26.1.6"``) and ``client_dir`` is
        ``src/opnsense_openapi/generated/v{resolved_with_underscores}/``.

    Raises:
        FileNotFoundError: If no spec can be resolved for ``version`` (the
            error originates in :func:`find_best_matching_spec`).
    """
    spec_path: Path = find_best_matching_spec(version)
    resolved_version: str = version_from_spec_path(spec_path)
    version_module: str = resolved_version.replace(".", "_")
    client_dir: Path = Path(__file__).parent.parent / "generated" / f"v{version_module}"
    return spec_path, resolved_version, client_dir


def _auto_generate_client(version: str) -> str:
    """Automatically generate Python client if spec exists but client doesn't.

    The generated-client directory is keyed off the *resolved* spec version,
    not the raw input. This means ``26.1.6_2`` and ``26.1.6_3`` both land in
    ``generated/v26_1_6/`` whenever the resolver maps them to
    ``opnsense-26.1.6.json``, and the second invocation finds an existing
    client without re-running codegen.

    Args:
        version: OPNsense version string (e.g., '24.7.1' or '26.1.6_2')

    Returns:
        The resolved spec version (e.g. ``"26.1.6"`` for an input of
        ``"26.1.6_2"``). Callers can use this to derive the canonical
        generated-client module path without re-resolving the spec.

    Raises:
        RuntimeError: With a cause-tagged message identifying which of three
            distinct failure modes occurred:

            - **Spec missing** — no committed spec resolves for ``version``.
              The message lists currently available versions and suggests
              ``opnsense-openapi generate {version}``.
            - **CLI missing** — ``openapi-python-client`` is not on
              ``PATH``. The message includes the resolved spec path and the
              correct install command (``uv tool install
              openapi-python-client``).
            - **Codegen failed** — ``openapi-python-client`` ran but exited
              non-zero. The message includes the version, spec path, return
              code, and captured stderr.
    """
    # Check if spec file exists and derive the canonical client dir.
    try:
        spec_path, resolved_version, client_dir = _resolved_module_dir(version)
    except FileNotFoundError as exc:
        available = list_available_specs()
        available_str = ", ".join(available) if available else "<none>"
        raise RuntimeError(
            f"No OpenAPI spec for version {version}; available=[{available_str}]. "
            f"Generate with: opnsense-openapi generate {version}"
        ) from exc

    if client_dir.exists():
        logger.debug(f"Generated client already exists at {client_dir}")
        return resolved_version

    # Check if openapi-python-client is available
    if not shutil.which("openapi-python-client"):
        raise RuntimeError(
            f"openapi-python-client is not on PATH; cannot generate the typed "
            f"client for version {version} (spec found at {spec_path}). "
            f"Install with `uv tool install openapi-python-client` and retry, "
            f"or run `opnsense-openapi generate {version}` manually."
        )

    # Generate the client
    logger.info(f"Auto-generating Python client for version {version}...")
    logger.info(f"Using spec: {spec_path}")
    logger.info(f"Output directory: {client_dir}")

    # Create a temporary config file to override the package name
    import os
    import tempfile

    config_data = {"package_name_override": "opnsense_openapi_client"}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as config_file:
        json.dump(config_data, config_file)
        config_path = config_file.name

    try:
        cmd = [
            "openapi-python-client",
            "generate",
            "--path",
            str(spec_path),
            "--output-path",
            str(client_dir),
            "--meta",
            "setup",  # Use setup to create the package structure
            "--config",
            config_path,
        ]

        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as exc:
            stderr_bytes = exc.stderr if isinstance(exc.stderr, bytes | bytearray) else b""
            stderr_text = (
                stderr_bytes.decode("utf-8", errors="replace").strip()
                if stderr_bytes
                else "<empty>"
            )
            raise RuntimeError(
                f"openapi-python-client failed for version {version} "
                f"(spec={spec_path}, returncode={exc.returncode}). "
                f"Re-run interactively for full output: "
                f"opnsense-openapi generate {version}. "
                f"Captured stderr: {stderr_text}"
            ) from exc

        logger.info(f"Successfully generated client for version {version}")
        return resolved_version
    finally:
        # Clean up temp config file
        with contextlib.suppress(Exception):
            os.unlink(config_path)


class OPNsenseClient:
    """Base HTTP client for OPNsense API with key/secret authentication.

    The OPNsense API uses API key and secret for authentication via HTTP Basic Auth.
    All requests return JSON and most operations use GET (retrieve) or POST (modify).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        api_secret: str | None = None,
        verify_ssl: bool = True,
        timeout: float = 30.0,
        spec_version: str | None = None,
        auto_detect_version: bool = True,
        auth: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize OPNsense API client.

        Args:
            base_url: Base URL of OPNsense instance (e.g., "https://opnsense.local")
            api_key: API key for authentication (Basic Auth)
            api_secret: API secret for authentication (Basic Auth)
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
            spec_version: Specific OpenAPI spec version to use (e.g., '24.7.1').
                         If None, will auto-detect from server.
            auto_detect_version: If True and spec_version is None, automatically
                                detect version from server
            auth: Custom httpx auth object (overrides api_key/api_secret)
            headers: Custom headers to include in requests
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        # Determine authentication method
        client_auth: Any = auth
        if client_auth is None and api_key and api_secret:
            client_auth = (api_key, api_secret)

        self._client: httpx.Client = httpx.Client(
            auth=client_auth,
            headers=headers,
            verify=verify_ssl,
            timeout=timeout,
            follow_redirects=True,
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
        parts: list[str] = ["api", module, controller, command]
        parts.extend(params)
        path: str = "/".join(parts)
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
        url: str = self._build_url(module, controller, command, *params)
        response: httpx.Response = self._client.get(url, params=query)
        response.raise_for_status()
        try:
            return cast(dict[str, Any], response.json())
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
        url: str = self._build_url(module, controller, command, *params)
        # Set Content-Type header for POST requests with JSON body
        headers: dict[str, str] = {"Content-Type": "application/json"} if json else {}
        response: httpx.Response = self._client.post(url, json=json, headers=headers)
        response.raise_for_status()
        try:
            return cast(dict[str, Any], response.json())
        except json.JSONDecodeError as e:  # type: ignore[union-attr]
            raise APIResponseError(f"Invalid JSON response from {url}: {e}", response.text) from e

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> OPNsenseClient:
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def detect_version(self) -> str:
        """Detect OPNsense version from the server.

        Tries multiple API endpoints to determine the version.

        Returns:
            Version string (e.g., '24.7.1')

        Raises:
            APIResponseError: If version cannot be retrieved from any endpoint
        """
        # List of endpoints to try for version detection
        version_endpoints: list[tuple[str, str, str]] = [
            # Try core/firmware/info first (more permissive)
            ("core", "firmware", "info"),
            # Fallback to status
            ("core", "firmware", "status"),
            # Try diagnostics endpoints
            ("diagnostics", "system", "systemInformation"),
        ]

        last_error: Exception | None = None
        for module, controller, command in version_endpoints:
            try:
                response: dict[str, Any] = self.get(module, controller, command)

                # Check for product_version at root level
                if "product_version" in response:
                    version: str = response["product_version"]
                    logger.debug(f"Got version from {module}/{controller}/{command}: {version}")
                    return version

                # Check for version in nested structure
                if "versions" in response and "product_version" in response["versions"]:
                    version = response["versions"]["product_version"]
                    logger.debug(f"Got version from {module}/{controller}/{command}: {version}")
                    return version

                # Check for product.product_version
                if "product" in response and "product_version" in response["product"]:
                    version = response["product"]["product_version"]
                    logger.debug(f"Got version from {module}/{controller}/{command}: {version}")
                    return version

            except Exception as e:
                logger.debug(f"Failed to get version from {module}/{controller}/{command}: {e}")
                last_error = e
                continue

        # If we get here, none of the endpoints worked
        error_msg: str = "Could not detect OPNsense version from any API endpoint"
        if last_error:
            error_msg += f". Last error: {last_error}"
        logger.error(error_msg)
        raise APIResponseError(error_msg, str(last_error) if last_error else "")

    @property
    def openapi(self) -> APIWrapper:
        """Get the OpenAPI wrapper instance (legacy).

        Lazily initializes the wrapper with the appropriate spec file.

        Returns:
            APIWrapper instance

        Raises:
            RuntimeError: If no version is available (neither specified nor detected)
            FileNotFoundError: If spec file for the version doesn't exist

        Note:
            This is the legacy dynamic wrapper. Consider using the `api` property
            for the generated client with full type hints instead.
        """
        if self._openapi is None:
            # Determine which version to use
            version: str | None = self._spec_version or self._detected_version

            if version is None:
                raise RuntimeError(
                    "No OPNsense version available. Either specify spec_version "
                    "or enable auto_detect_version."
                )

            # Find the best matching spec file
            spec_path: Path = find_best_matching_spec(version)
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

    @property
    def api(self) -> Any:
        """Get the generated API client with version-agnostic access.

        Auto-detects the OPNsense version and returns a dynamic API wrapper
        that doesn't require version-specific imports.

        Returns:
            GeneratedAPI wrapper for version-agnostic access

        Raises:
            RuntimeError: If no version is available, the spec is missing,
                ``openapi-python-client`` is not on ``PATH``, or codegen
                failed. The message identifies which of those occurred (see
                :func:`_auto_generate_client`).

        Example (No version-specific imports needed!):
            >>> client = OPNsenseClient(..., auto_detect_version=True)
            >>> api = client.api
            >>>
            >>> # Call any API function without knowing the version
            >>> info = api.core.firmware_info()  # Auto-calls sync()
            >>> aliases = api.firewall.alias_search_item()
            >>>
            >>> # Or use explicit methods
            >>> info = api.core.firmware_info.sync()
            >>> response = api.core.firmware_info.sync_detailed()
        """
        # Determine which version to use
        version: str | None = self._spec_version or self._detected_version

        if version is None:
            raise RuntimeError(
                "No OPNsense version available. Either specify spec_version "
                "or enable auto_detect_version."
            )

        # Auto-generate (or confirm) the typed client. The helper raises
        # ``RuntimeError`` with a cause-tagged message on any failure mode
        # (spec missing, CLI missing, codegen failed) and returns the
        # *resolved* spec version on success — which is what we need below
        # to build the importlib path.
        resolved_version: str = _auto_generate_client(version)

        # Import the generated client for the *resolved* version, so that
        # ``26.1.6`` and ``26.1.6_2`` share a single generated client.
        version_module: str = resolved_version.replace(".", "_")
        module_path: str = f"opnsense_openapi.generated.v{version_module}.opnsense_openapi_client"

        try:
            import importlib

            from .generated_api import GeneratedAPI

            generated: Any = importlib.import_module(module_path)

            # Create a Client instance and inject our authenticated httpx client
            api_client: Any = generated.Client(base_url=f"{self.base_url}/api")
            api_client.set_httpx_client(self._client)

            # Wrap in GeneratedAPI for version-agnostic access. Pass the
            # resolved version so ``GeneratedAPI`` builds importlib paths
            # against the directory ``_auto_generate_client`` populated.
            return GeneratedAPI(api_client, resolved_version)

        except ImportError as e:
            # This should rarely happen now that we auto-generate, but keep as fallback
            raise RuntimeError(
                f"Failed to import generated client for version {version}. "
                f"Try running: opnsense-openapi build-client --version {version}"
            ) from e

    def list_endpoints(self) -> list[tuple[str, str, str]]:
        """List all available API endpoints from the OpenAPI spec.

        Returns:
            List of (path, METHOD, summary) tuples

        Raises:
            RuntimeError: If OpenAPI wrapper is not available
        """
        if self._openapi is None:
            # force initialization of _openapi property
            _ = self.openapi
        return self.openapi.list_endpoints()

    def get_endpoint_info(self, path_template: str, method: str = "GET") -> SuggestedParameters:
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
        if self._openapi is None:
            # force initialization of _openapi property
            _ = self.openapi
        return self.openapi.suggest_parameters(path_template, method)
