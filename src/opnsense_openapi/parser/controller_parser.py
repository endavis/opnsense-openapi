"""Parse PHP controller files to extract API endpoint definitions."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Parent that lives outside the controllers tree; the chain ends there without a warning.
_MVC_ROOT_CONTROLLER = "OPNsense\\Mvc\\Controller"


@dataclass
class ApiEndpoint:
    """Represents a single API endpoint extracted from a controller."""

    name: str  # Method name without 'Action' suffix
    method: str  # HTTP method (GET or POST)
    description: str  # Extracted from docblock
    parameters: list[str]  # Method parameters, in signature order
    # Trailing parameters with a PHP default; always a suffix of ``parameters``
    optional_parameters: list[str] = field(default_factory=list)


@dataclass
class ApiController:
    """Represents an API controller with its endpoints."""

    module: str  # e.g., "Firewall"
    controller: str  # e.g., "AliasUtil"
    base_class: str  # e.g., "ApiControllerBase"
    endpoints: list[ApiEndpoint]
    model_class: str | None = None  # e.g., "OPNsense\\Firewall\\Alias"
    model_name: str | None = None  # e.g., "dnsmasq" (from $internalModelName)
    is_abstract: bool = False  # True for abstract base controllers (never routable)
    namespace: str = ""  # Full PHP namespace, e.g., "OPNsense\\Firewall\\Api"


@dataclass
class _ClassInfo:
    """One PHP class found while indexing a controllers tree (private)."""

    path: Path
    fqn: str
    name: str
    namespace: str
    is_abstract: bool
    extends: str | None
    uses: dict[str, str]
    endpoints: list[ApiEndpoint]
    model_class: str | None
    model_name: str | None


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
        r"^\s*(abstract\s+|final\s+)?class\s+(\w+)(?:\s+extends\s+([\\\w]+))?", re.MULTILINE
    )

    # Pattern to extract any namespace
    GENERIC_NAMESPACE_PATTERN = re.compile(r"^\s*namespace\s+([\w\\]+)\s*;", re.MULTILINE)

    # Pattern to extract ``use`` imports
    USE_PATTERN = re.compile(r"^\s*use\s+([\w\\]+)(?:\s+as\s+(\w+))?\s*;", re.MULTILINE)

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

        info = self._parse_class_file(file_path)
        if info is None or info.extends is None:
            return None
        return self._to_controller(info, info.endpoints, info.model_class, info.model_name)

    def _to_controller(
        self,
        info: _ClassInfo,
        endpoints: list[ApiEndpoint],
        model_class: str | None,
        model_name: str | None,
    ) -> ApiController | None:
        """Build an ApiController from an indexed class, or None if not an Api controller."""
        module_match = self.NAMESPACE_PATTERN.fullmatch(f"namespace {info.namespace};")
        if not module_match or info.extends is None:
            return None
        return ApiController(
            module=module_match.group(1),
            controller=info.name.replace("Controller", ""),
            base_class=info.extends.rsplit("\\", 1)[-1],
            endpoints=endpoints,
            model_class=model_class,
            model_name=model_name,
            is_abstract=info.is_abstract,
            namespace=info.namespace,
        )

    def _parse_class_file(self, file_path: Path) -> _ClassInfo | None:
        """Index the class declared in a PHP file, whatever its parent or location.

        Args:
            file_path: Path to a PHP file

        Returns:
            _ClassInfo, or None when the file has no namespace or class
        """
        content = file_path.read_text(encoding="utf-8")

        namespace_match = self.GENERIC_NAMESPACE_PATTERN.search(content)
        if not namespace_match:
            return None
        namespace = namespace_match.group(1)

        class_match = self.CLASS_PATTERN.search(content)
        if not class_match:
            return None

        uses = {
            (m.group(2) or m.group(1).rsplit("\\", 1)[-1]): m.group(1)
            for m in self.USE_PATTERN.finditer(content)
        }
        model_match = self.MODEL_CLASS_PATTERN.search(content)
        model_name_match = self.MODEL_NAME_PATTERN.search(content)
        name = class_match.group(2)

        return _ClassInfo(
            path=file_path,
            fqn=f"{namespace}\\{name}",
            name=name,
            namespace=namespace,
            is_abstract=bool(class_match.group(1) and "abstract" in class_match.group(1)),
            extends=class_match.group(3),
            uses=uses,
            endpoints=self._extract_endpoints(content),
            model_class=model_match.group(1) if model_match else None,
            model_name=model_name_match.group(1) if model_name_match else None,
        )

    @staticmethod
    def _resolve_parent(info: _ClassInfo, index: dict[str, _ClassInfo]) -> str | None:
        """Resolve a class's ``extends`` target to a fully qualified name.

        Order: FQN as written, matching ``use`` import, same namespace, ``OPNsense\\Base``.
        The first candidate present in the index wins; otherwise the most specific guess
        is returned so the caller can report it.

        Args:
            info: The child class
            index: All indexed classes by FQN

        Returns:
            Parent FQN, or None when the class has no parent
        """
        if info.extends is None:
            return None
        parent = info.extends
        if "\\" in parent:
            return parent.lstrip("\\")
        candidates = []
        if parent in info.uses:
            candidates.append(info.uses[parent])
        candidates.append(f"{info.namespace}\\{parent}")
        candidates.append(f"OPNsense\\Base\\{parent}")
        for candidate in candidates:
            if candidate in index:
                return candidate
        return candidates[0]

    def _merge_inherited(
        self, info: _ClassInfo, index: dict[str, _ClassInfo], warned: set[str]
    ) -> tuple[list[ApiEndpoint], str | None, str | None]:
        """Merge a class's actions with those of its ancestors.

        Own actions come first, then each ancestor's, nearest first; a name already present
        (case-insensitive, as PHP method names are) is skipped, so overrides win. Model
        properties come from the nearest class that declares them.

        Args:
            info: The concrete class
            index: All indexed classes by FQN
            warned: FQNs already reported as unresolved (updated in place)

        Returns:
            Tuple of (endpoints, model_class, model_name)
        """
        endpoints: list[ApiEndpoint] = []
        seen: set[str] = set()
        model_class: str | None = None
        model_name: str | None = None
        visited: set[str] = set()
        current: _ClassInfo | None = info

        while current is not None and current.fqn not in visited:
            visited.add(current.fqn)
            for endpoint in current.endpoints:
                if endpoint.name.lower() not in seen:
                    seen.add(endpoint.name.lower())
                    endpoints.append(endpoint)
            model_class = model_class or current.model_class
            model_name = model_name or current.model_name

            parent_fqn = self._resolve_parent(current, index)
            if parent_fqn is None:
                break
            current = index.get(parent_fqn)
            if current is None and parent_fqn != _MVC_ROOT_CONTROLLER and parent_fqn not in warned:
                warned.add(parent_fqn)
                logger.warning(
                    "Parent class %s of %s not found; inherited actions are missing",
                    parent_fqn,
                    info.fqn,
                )

        return endpoints, model_class, model_name

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
            optional_parameters = self._parse_optional_parameters(params_str)

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
                    optional_parameters=optional_parameters,
                )
            )

        return endpoints

    @staticmethod
    def _parse_signature(params_str: str) -> list[tuple[str, bool]]:
        """Parse a signature into ``(name, has_default)`` pairs in order.

        Args:
            params_str: Parameter string from method signature

        Returns:
            List of (parameter name, has PHP default) tuples
        """
        return [
            (m.group(1), m.group(2) is not None) for m in re.finditer(r"\$(\w+)\s*(=)?", params_str)
        ]

    def _parse_parameters(self, params_str: str) -> list[str]:
        """Parse method parameters from parameter string.

        Args:
            params_str: Parameter string from method signature

        Returns:
            List of parameter names
        """
        return [name for name, _ in self._parse_signature(params_str)]

    def _parse_optional_parameters(self, params_str: str) -> list[str]:
        """Return the longest trailing run of parameters that have a PHP default.

        Args:
            params_str: Parameter string from method signature

        Returns:
            List of optional parameter names, in signature order
        """
        optional: list[str] = []
        for name, has_default in reversed(self._parse_signature(params_str)):
            if not has_default:
                break
            optional.append(name)
        optional.reverse()
        return optional

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

        # Pass 1: index every class. Sorted, because rglob yields filesystem order,
        # which differs between machines and would reorder the spec (#138).
        index: dict[str, _ClassInfo] = {}
        for php_file in sorted(directory.rglob("*.php")):
            info = self._parse_class_file(php_file)
            if info:
                index[info.fqn] = info

        # Pass 2: emit concrete Api controllers with their inherited actions merged in.
        warned: set[str] = set()
        for info in index.values():
            if info.is_abstract or "Api" not in info.path.parts:
                continue
            if not info.path.name.endswith("Controller.php") or not info.name.endswith(
                "Controller"
            ):
                continue
            endpoints, model_class, model_name = self._merge_inherited(info, index, warned)
            controller = self._to_controller(info, endpoints, model_class, model_name)
            if controller:
                controllers.append(controller)

        return controllers
