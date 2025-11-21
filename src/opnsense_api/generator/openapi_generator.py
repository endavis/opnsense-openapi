"""Generate OpenAPI JSON specification from parsed API controllers."""

import json
from pathlib import Path
from typing import Any

from ..parser import ApiController, ApiEndpoint, ModelDefinition, ModelParser
from ..utils import to_snake_case


class OpenApiGenerator:
    """Generate OpenAPI 3.0 specification from parsed API controllers."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize OpenAPI generator.

        Args:
            output_dir: Directory to write generated files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_parser = ModelParser()
        self.models: dict[str, ModelDefinition] = {}

    def generate(
        self,
        controllers: list[ApiController],
        version: str,
        models_dir: Path | None = None,
    ) -> Path:
        """Generate OpenAPI specification for all controllers.

        Args:
            controllers: List of parsed API controllers
            version: OPNsense version
            models_dir: Directory containing model XML files

        Returns:
            Path to generated OpenAPI JSON file
        """
        # Parse models if directory provided
        if models_dir:
            self.models = self.model_parser.parse_directory(models_dir)

        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {
                "title": "OPNsense API",
                "version": version,
                "description": f"Auto-generated OpenAPI specification for OPNsense {version}",
            },
            "servers": [{"url": "https://{host}/api", "variables": {"host": {"default": "localhost"}}}],
            "paths": {},
            "components": {
                "securitySchemes": {
                    "basicAuth": {"type": "http", "scheme": "basic"}
                }
            },
            "security": [{"basicAuth": []}],
        }

        for controller in controllers:
            self._add_controller_paths(spec, controller)

        output_path = self.output_dir / f"opnsense-{version}.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)

        return output_path

    def _add_controller_paths(self, spec: dict[str, Any], controller: ApiController) -> None:
        """Add paths for a controller to the spec.

        Args:
            spec: OpenAPI spec dictionary
            controller: Controller to add
        """
        module = controller.module.lower()
        ctrl_name = to_snake_case(controller.controller)

        # Get model schema if available
        model_schema = self._get_model_schema(controller)

        for endpoint in controller.endpoints:
            # Build path with path parameters (e.g., {uuid})
            path_params = self._get_path_params(endpoint.parameters)
            other_params = [p for p in endpoint.parameters if p not in path_params]

            base_path = f"/{module}/{ctrl_name}/{to_snake_case(endpoint.name)}"
            if path_params:
                path = base_path + "/" + "/".join(f"{{{p}}}" for p in path_params)
            else:
                path = base_path

            method = endpoint.method.lower()

            # Determine response schema
            response_schema: dict[str, Any] = {"type": "object"}
            if model_schema and self._is_model_endpoint(endpoint.name):
                response_schema = model_schema

            operation: dict[str, Any] = {
                "operationId": f"{module}_{ctrl_name}_{to_snake_case(endpoint.name)}",
                "tags": [controller.module],
                "summary": endpoint.description or endpoint.name,
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {"application/json": {"schema": response_schema}},
                    }
                },
            }

            # Add path parameters
            if path_params:
                operation["parameters"] = [
                    {
                        "name": param,
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                    for param in path_params
                ]

            # Add query params or request body for remaining params
            if other_params:
                if method == "get":
                    query_params = [
                        {
                            "name": param,
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                        for param in other_params
                    ]
                    if "parameters" in operation:
                        operation["parameters"].extend(query_params)
                    else:
                        operation["parameters"] = query_params
                else:
                    # Use model schema for request body if available
                    request_schema: dict[str, Any] = {
                        "type": "object",
                        "properties": {
                            param: {"type": "string"} for param in other_params
                        },
                    }
                    if model_schema and self._is_model_endpoint(endpoint.name):
                        request_schema = model_schema

                    operation["requestBody"] = {
                        "content": {"application/json": {"schema": request_schema}}
                    }

            spec["paths"][path] = {method: operation}

    def _get_path_params(self, parameters: list[str]) -> list[str]:
        """Identify which parameters should be path parameters.

        Args:
            parameters: List of parameter names

        Returns:
            List of parameter names that should be in the path
        """
        # Common path parameter patterns in OPNsense
        path_param_names = {"uuid", "id", "name", "number", "index"}
        return [p for p in parameters if p.lower() in path_param_names]

    def _get_model_schema(self, controller: ApiController) -> dict[str, Any] | None:
        """Get JSON schema for controller's model.

        Args:
            controller: Controller to get model for

        Returns:
            JSON Schema dict or None
        """
        if not controller.model_class or controller.model_class not in self.models:
            return None

        model = self.models[controller.model_class]
        # Find the main container (usually has the most fields)
        best_container = "root"
        max_fields = 0
        for container, fields in model.fields.items():
            if len(fields) > max_fields:
                max_fields = len(fields)
                best_container = container

        return self.model_parser.to_json_schema(model, best_container)

    def _is_model_endpoint(self, endpoint_name: str) -> bool:
        """Check if endpoint likely returns/accepts model data.

        Args:
            endpoint_name: Endpoint name

        Returns:
            True if endpoint uses model data
        """
        model_patterns = ["get", "set", "add", "search", "item"]
        return any(p in endpoint_name.lower() for p in model_patterns)
