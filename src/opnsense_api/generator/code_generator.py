"""Generate Python client code from parsed API controllers."""

from pathlib import Path
from typing import TextIO

from ..parser import ApiController, ApiEndpoint
from ..utils import to_class_name, to_snake_case


class CodeGenerator:
    """Generate Python client classes from parsed API controllers."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize code generator.

        Args:
            output_dir: Directory to write generated files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, controllers: list[ApiController], version: str) -> None:
        """Generate Python client code for all controllers.

        Args:
            controllers: List of parsed API controllers
            version: OPNsense version (for documentation)
        """
        # Group controllers by module
        modules: dict[str, list[ApiController]] = {}
        for controller in controllers:
            module_name = controller.module.lower()
            if module_name not in modules:
                modules[module_name] = []
            modules[module_name].append(controller)

        # Generate __init__.py for main package
        self._generate_main_init(modules, version)

        # Generate module files
        for module_name, module_controllers in modules.items():
            self._generate_module(module_name, module_controllers)

    def _generate_main_init(self, modules: dict[str, list[ApiController]], version: str) -> None:
        """Generate main __init__.py file.

        Args:
            modules: Dictionary of module names to controllers
            version: OPNsense version
        """
        init_path = self.output_dir / "__init__.py"

        with init_path.open("w", encoding="utf-8") as f:
            f.write(f'"""Generated OPNsense API client for version {version}."""\n\n')
            f.write("from opnsense_api.client import OPNsenseClient\n\n")

            # Import all module classes
            for module_name in sorted(modules.keys()):
                f.write(f"from .{module_name} import {to_class_name(module_name)}\n")

            f.write("\n__all__ = [\n")
            f.write('    "OPNsenseClient",\n')
            for module_name in sorted(modules.keys()):
                f.write(f'    "{to_class_name(module_name)}",\n')
            f.write("]\n")

    def _generate_module(self, module_name: str, controllers: list[ApiController]) -> None:
        """Generate Python module file for a group of controllers.

        Args:
            module_name: Name of the module (lowercase)
            controllers: List of controllers in this module
        """
        module_path = self.output_dir / f"{module_name}.py"
        class_name = to_class_name(module_name)

        with module_path.open("w", encoding="utf-8") as f:
            # Write header
            f.write(f'"""OPNsense {class_name} API module."""\n\n')
            f.write("from typing import Any\n\n")
            f.write("from opnsense_api.client import OPNsenseClient\n\n\n")

            # Write main module class
            f.write(f"class {class_name}:\n")
            f.write(f'    """{class_name} API module.\n\n')
            f.write(f"    Contains controllers:\n")
            for controller in controllers:
                f.write(f"    - {controller.controller}\n")
            f.write('    """\n\n')

            f.write("    def __init__(self, client: OPNsenseClient) -> None:\n")
            f.write("        self._client = client\n")

            # Create properties for each controller
            for controller in controllers:
                controller_var = to_snake_case(controller.controller)
                f.write(f"        self.{controller_var} = self.{controller.controller}(client)\n")

            f.write("\n")

            # Generate nested controller classes
            for controller in controllers:
                self._generate_controller_class(f, module_name, controller)

    def _generate_controller_class(
        self, f: TextIO, module_name: str, controller: ApiController
    ) -> None:
        """Generate a controller class with its endpoint methods.

        Args:
            f: File object to write to
            module_name: Name of the parent module
            controller: Controller to generate
        """
        f.write(f"    class {controller.controller}:\n")
        f.write(f'        """{controller.controller} controller.\n\n')
        if controller.endpoints:
            f.write("        Available endpoints:\n")
            for endpoint in controller.endpoints:
                f.write(f"        - {endpoint.name}: {endpoint.description or 'No description'}\n")
        f.write('        """\n\n')

        f.write("        def __init__(self, client: OPNsenseClient) -> None:\n")
        f.write("            self._client = client\n")
        controller_snake = to_snake_case(controller.controller)
        f.write(f'            self._module = "{module_name}"\n')
        f.write(f'            self._controller = "{controller_snake}"\n\n')

        # Generate methods for each endpoint
        for endpoint in controller.endpoints:
            self._generate_endpoint_method(f, endpoint)

        f.write("\n")

    def _generate_endpoint_method(self, f: TextIO, endpoint: ApiEndpoint) -> None:
        """Generate a method for an API endpoint.

        Args:
            f: File object to write to
            endpoint: Endpoint to generate method for
        """
        method_name = to_snake_case(endpoint.name)
        param_sig = ", ".join(f"{p}: Any" for p in endpoint.parameters)
        if param_sig:
            param_sig = f", {param_sig}"

        f.write(f"        def {method_name}(self{param_sig}) -> dict[str, Any]:\n")

        # Write docstring
        f.write(f'            """{endpoint.description or endpoint.name}.\n\n')
        if endpoint.parameters:
            f.write("            Args:\n")
            for param in endpoint.parameters:
                f.write(f"                {param}: Parameter for the API call\n")
        f.write("\n            Returns:\n")
        f.write("                API response as dictionary\n")
        f.write('            """\n')

        # Generate method call
        if endpoint.method == "GET":
            f.write("            return self._client.get(\n")
        else:
            f.write("            return self._client.post(\n")

        f.write("                self._module,\n")
        f.write("                self._controller,\n")
        f.write(f'                "{to_snake_case(endpoint.name)}",\n')

        if endpoint.method == "POST" and endpoint.parameters:
            # For POST, pass parameters as JSON
            json_params = ", ".join(f'"{p}": {p}' for p in endpoint.parameters)
            f.write(f"                json={{{json_params}}},\n")

        f.write("            )\n\n")
