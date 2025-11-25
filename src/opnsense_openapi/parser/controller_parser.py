"""Parse PHP controller files to extract API endpoint definitions."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ApiEndpoint:
    """Represents a single API endpoint extracted from a controller."""

    name: str  # Method name without 'Action' suffix
    method: str  # HTTP method (GET or POST)
    description: str  # Extracted from docblock
    parameters: list[str]  # Method parameters


@dataclass
class ApiController:
    """Represents an API controller with its endpoints."""

    module: str  # e.g., "Firewall"
    controller: str  # e.g., "AliasUtil"
    base_class: str  # e.g., "ApiControllerBase"
    endpoints: list[ApiEndpoint]
    model_class: str | None = None  # e.g., "OPNsense\\Firewall\\Alias"
    model_name: str | None = None  # e.g., "dnsmasq" (from $internalModelName)


class ControllerParser:
    """Parser for extracting API information from PHP controller files.

    This parser uses regex to extract:
    - Controller class name and namespace
    - Base class (ApiControllerBase, ApiMutableModelControllerBase, etc.)
    - Public methods ending in 'Action'
    - Method parameters and docblocks
    """

    # Pattern to extract namespace
    NAMESPACE_PATTERN = re.compile(r"namespace\s+OPNsense\\(\w+)\\Api;")

    # Pattern to extract class definition
    CLASS_PATTERN = re.compile(
        r"class\s+(\w+Controller)\s+extends\s+(Api\w*(?:ControllerBase|Controller))"
    )

    # Pattern to extract public methods (actions)
    METHOD_PATTERN = re.compile(r"public\s+function\s+(\w+Action)\s*\(([^)]*)\)", re.MULTILINE)

    # Pattern to extract docblock comments
    DOCBLOCK_PATTERN = re.compile(r"/\*\*\s*(.*?)\s*\*/", re.DOTALL)

    # Pattern to extract internal model class
    MODEL_CLASS_PATTERN = re.compile(r"\$internalModelClass\s*=\s*['\"]([^'\"]+)['\"]")

    # Pattern to extract internal model name
    MODEL_NAME_PATTERN = re.compile(r"\$internalModelName\s*=\s*['\"]([^'\"]+)['\"]")

    def parse_controller_file(self, file_path: Path) -> ApiController | None:
        """Parse a PHP controller file to extract API endpoint information.

        Args:
            file_path: Path to the PHP controller file

        Returns:
            ApiController object if valid API controller, None otherwise
        """
        if not file_path.exists() or not file_path.name.endswith("Controller.php"):
            return None

        content = file_path.read_text(encoding="utf-8")

        # Extract namespace (module)
        namespace_match = self.NAMESPACE_PATTERN.search(content)
        if not namespace_match:
            return None
        module = namespace_match.group(1)

        # Extract class name and base class
        class_match = self.CLASS_PATTERN.search(content)
        if not class_match:
            return None
        controller_class = class_match.group(1)
        base_class = class_match.group(2)

        # Remove 'Controller' suffix from class name
        controller_name = controller_class.replace("Controller", "")

        # Extract all public action methods
        endpoints = self._extract_endpoints(content)

        # Extract model class if present
        model_match = self.MODEL_CLASS_PATTERN.search(content)
        model_class = model_match.group(1) if model_match else None

        # Extract model name if present
        model_name_match = self.MODEL_NAME_PATTERN.search(content)
        model_name = model_name_match.group(1) if model_name_match else None

        return ApiController(
            module=module,
            controller=controller_name,
            base_class=base_class,
            endpoints=endpoints,
            model_class=model_class,
            model_name=model_name,
        )

    def _extract_endpoints(self, content: str) -> list[ApiEndpoint]:
        """Extract all action methods from controller content.

        Args:
            content: PHP file content

        Returns:
            List of ApiEndpoint objects
        """
        endpoints: list[ApiEndpoint] = []

        for match in self.METHOD_PATTERN.finditer(content):
            method_name = match.group(1)
            params_str = match.group(2).strip()

            # Remove 'Action' suffix
            endpoint_name = method_name.replace("Action", "")

            # Parse parameters
            parameters = self._parse_parameters(params_str)

            # Determine HTTP method (heuristic: methods with parameters often use POST)
            # Methods like 'get', 'search', 'find', 'list' are typically GET
            http_method = self._guess_http_method(endpoint_name, parameters)

            # Try to extract description from docblock before method
            description = self._extract_description(content, method_name)

            endpoints.append(
                ApiEndpoint(
                    name=endpoint_name,
                    method=http_method,
                    description=description,
                    parameters=parameters,
                )
            )

        return endpoints

    def _parse_parameters(self, params_str: str) -> list[str]:
        """Parse method parameters from parameter string.

        Args:
            params_str: Parameter string from method signature

        Returns:
            List of parameter names
        """
        if not params_str:
            return []

        params = []
        for param in params_str.split(","):
            param = param.strip()
            if param:
                # Extract parameter name (after $)
                match = re.search(r"\$(\w+)", param)
                if match:
                    params.append(match.group(1))

        return params

    def _guess_http_method(self, endpoint_name: str, parameters: list[str]) -> str:
        """Guess HTTP method based on endpoint name and parameters.

        Args:
            endpoint_name: Name of the endpoint
            parameters: List of parameter names

        Returns:
            'GET' or 'POST'
        """
        # Common patterns for GET methods
        # Removed 'search' and 'find' as they often require POST for complex parameters
        get_patterns = ["get", "list", "export", "show", "fetch", "info", "overview", "status"]

        endpoint_lower = endpoint_name.lower()

        # Check if endpoint name contains GET-like patterns
        if any(pattern in endpoint_lower for pattern in get_patterns):
            return "GET"

        # Common patterns for POST methods
        post_patterns = ["set", "add", "del", "save", "update", "create", "toggle", "reconfigure"]

        if any(pattern in endpoint_lower for pattern in post_patterns):
            return "POST"

        # Default to POST for safety as OPNsense heavily relies on POST
        return "POST"

    def _extract_description(self, content: str, method_name: str) -> str:
        """Extract description from docblock comment before method.

        Args:
            content: PHP file content
            method_name: Method name to find

        Returns:
            Description string or empty string
        """
        # Find the method position
        method_pattern = rf"public\s+function\s+{method_name}"
        match = re.search(method_pattern, content)
        if not match:
            return ""

        # Look for docblock before method
        before_method = content[: match.start()]
        docblock_matches = list(self.DOCBLOCK_PATTERN.finditer(before_method))

        if docblock_matches:
            # Get the last docblock before the method
            last_docblock = docblock_matches[-1]
            docblock_text = last_docblock.group(1)

            # Extract first meaningful line (skip @tags)
            for line in docblock_text.split("\n"):
                line = line.strip().lstrip("*").strip()
                if line and not line.startswith("@"):
                    return line

        return ""

    def parse_directory(self, directory: Path) -> list[ApiController]:
        """Parse all controller files in a directory recursively.

        Args:
            directory: Directory containing controller files

        Returns:
            List of ApiController objects
        """
        controllers: list[ApiController] = []

        if not directory.exists():
            return controllers

        # Find all PHP controller files
        for php_file in directory.rglob("*Controller.php"):
            # Only parse files in 'Api' directories
            if "Api" in php_file.parts:
                controller = self.parse_controller_file(php_file)
                if controller:
                    controllers.append(controller)

        return controllers
