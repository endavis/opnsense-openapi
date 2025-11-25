"""Dynamic wrapper for generated API clients that doesn't require version-specific imports."""

from typing import Any


class GeneratedAPI:
    """Wrapper that provides version-agnostic access to generated API functions.

    This allows you to use the generated client without knowing the version upfront:

    Example:
        >>> client = OPNsenseClient(..., auto_detect_version=True)
        >>> api = client.api
        >>>
        >>> # No version-specific imports needed!
        >>> info = api.core.firmware_info()  # Calls sync() automatically
        >>> status = api.core.firmware_status()
        >>>
        >>> # Access any module/function dynamically
        >>> aliases = api.firewall.alias_search_item()
    """

    def __init__(self, generated_client: Any, version: str) -> None:
        """Initialize the dynamic API wrapper.

        Args:
            generated_client: The generated Client instance
            version: Version string (e.g., "25.7.6")
        """
        self._client = generated_client
        self._version = version
        self._version_module = version.replace(".", "_")

    def __getattr__(self, module_name: str) -> "ModuleProxy":
        """Dynamically access API modules (core, firewall, etc.)."""
        return ModuleProxy(self._client, self._version_module, module_name)

    def __repr__(self) -> str:
        return f"GeneratedAPI(version={self._version})"


class ModuleProxy:
    """Proxy for a generated API module (e.g., core, firewall)."""

    def __init__(self, client: Any, version_module: str, module_name: str) -> None:
        """Initialize module proxy.

        Args:
            client: Generated client instance
            version_module: Version with underscores (e.g., "25_7_6")
            module_name: Module name (e.g., "core", "firewall")
        """
        self._client = client
        self._version_module = version_module
        self._module_name = module_name

    def __getattr__(self, function_name: str) -> "FunctionProxy":
        """Dynamically access API functions within the module."""
        return FunctionProxy(self._client, self._version_module, self._module_name, function_name)

    def __repr__(self) -> str:
        return f"ModuleProxy(module={self._module_name})"


class FunctionProxy:
    """Proxy for a generated API function."""

    def __init__(
        self, client: Any, version_module: str, module_name: str, function_name: str
    ) -> None:
        """Initialize function proxy.

        Args:
            client: Generated client instance
            version_module: Version with underscores
            module_name: Module name (e.g., "core")
            function_name: Function name (e.g., "firmware_info")
        """
        self._client = client
        self._version_module = version_module
        self._module_name = module_name
        self._function_name = function_name
        self._function_module: Any = None  # Initialize as Any to avoid mypy error

    def _load_function_module(self) -> Any:
        """Lazy-load the generated function module."""
        if self._function_module is None:
            import importlib

            # Build module path:
            # opnsense_openapi.generated.v25_7_6.opnsense_openapi_client.api.core.core_firmware_info
            function_module_name = f"{self._module_name}_{self._function_name}"
            module_path = (
                f"opnsense_openapi.generated.v{self._version_module}."
                f"opnsense_openapi_client.api.{self._module_name}.{function_module_name}"
            )

            try:
                self._function_module = importlib.import_module(module_path)
            except ImportError as e:
                raise AttributeError(
                    f"API function '{self._module_name}.{self._function_name}' not found. "
                    f"Make sure the generated client exists for version {self._version_module}."
                ) from e

        return self._function_module

    def __call__(self, **kwargs: Any) -> Any:
        """Call the function's sync() method.

        This is a convenience that automatically calls .sync(client=...).
        For more control, use .sync(), .sync_detailed(), .asyncio(), etc.
        """
        return self.sync(**kwargs)

    def sync(self, **kwargs: Any) -> Any:
        """Call the generated sync() function."""
        module: Any = self._load_function_module()
        return module.sync(client=self._client, **kwargs)

    def sync_detailed(self, **kwargs: Any) -> Any:
        """Call the generated sync_detailed() function."""
        module: Any = self._load_function_module()
        return module.sync_detailed(client=self._client, **kwargs)

    async def asyncio(self, **kwargs: Any) -> Any:
        """Call the generated asyncio() function."""
        module: Any = self._load_function_module()
        return await module.asyncio(client=self._client, **kwargs)

    async def asyncio_detailed(self, **kwargs: Any) -> Any:
        """Call the generated asyncio_detailed() function."""
        module: Any = self._load_function_module()
        return await module.asyncio_detailed(client=self._client, **kwargs)

    def __repr__(self) -> str:
        return f"FunctionProxy(function={self._module_name}.{self._function_name})"
