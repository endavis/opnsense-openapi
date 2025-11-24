"""Generate OpenAPI JSON specification from parsed API controllers."""

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# We keep these imports to match your project structure,
# though the logic below handles parsing internally for better accuracy.
from ..parser import ApiController

logger = logging.getLogger(__name__)

# ================= TYPE MAPPING =================
TYPE_MAP = {
    "IntegerField": {"type": "integer"},
    "TextField": {"type": "string"},
    "BooleanField": {"type": "boolean"},
    "NetworkField": {"type": "string", "format": "ipv4"},
    "OptionField": {"type": "string", "description": "Dropdown selection"},
    "ModelRelationField": {"type": "string", "description": "UUID reference"},
    "CSVListField": {"type": "string", "description": "Comma separated values"},
    "CertificateField": {"type": "string", "description": "Certificate Data"},
    "EmailField": {"type": "string", "format": "email"},
}

class OpenApiGenerator:
    """Generate OpenAPI 3.0 specification from parsed API controllers."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize OpenAPI generator.

        Args:
            output_dir: Directory to write generated files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.spec: dict[str, Any] = {}
        self.models_dir: Path | None = None

    def generate(
        self,
        controllers: list[ApiController],
        version: str,
        models_dir: Path | None = None,
        controllers_dir: Path | None = None,
    ) -> Path:
        """Generate OpenAPI specification for all controllers.

        Args:
            controllers: List of parsed API controllers
            version: OPNsense version
            models_dir: Directory containing model XML files
            controllers_dir: Directory containing controller PHP files (unused in v3 logic)

        Returns:
            Path to generated OpenAPI JSON file
        """
        self.models_dir = models_dir

        self.spec = {
            "openapi": "3.0.3",
            "info": {
                "title": "OPNsense API",
                "version": version,
                "description": f"Auto-generated OpenAPI specification for OPNsense {version}. Includes Enum resolution and UUID path parameters.",
            },
            "servers": [
                {"url": "https://{host}/api", "variables": {"host": {"default": "192.168.1.1"}}}
            ],
            "paths": {},
            "components": {
                "schemas": {
                    "StatusResponse": {
                        "type": "object",
                        "properties": {
                            "result": {"type": "string", "example": "saved"},
                            "validations": {"type": "object", "description": "Validation errors if failed"}
                        }
                    }
                },
                "securitySchemes": {
                    "basicAuth": {"type": "http", "scheme": "basic"},
                    "apiKey": {"type": "apiKey", "in": "header", "name": "Authorization"}
                }
            },
            "security": [{"basicAuth": []}, {"apiKey": []}],
        }

        for controller in controllers:
            self._process_controller(controller)

        output_path = self.output_dir / f"opnsense-{version}.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(self.spec, f, indent=2)

        logger.info(f"Generated OpenAPI spec at {output_path}")
        return output_path

    def _process_controller(self, controller: ApiController) -> None:
        """Process a single controller to add schemas and paths."""
        module = controller.module
        # Clean controller name (e.g. "AliasController" -> "Alias")
        ctrl_name = controller.controller.replace("Controller", "")

        # 1. Try to find and parse the Model XML
        # This generates the "OPNsenseFirewallAlias" schema
        schema_name = f"OPNsense{module}{ctrl_name}"
        model_schema = self._find_and_parse_model("OPNsense", module, ctrl_name)

        if model_schema:
            self.spec['components']['schemas'][schema_name] = model_schema
            self._create_search_schema(schema_name)

        # 2. Process endpoints
        # controller.endpoints is expected to be a list of endpoint objects with a 'name' attribute
        for endpoint in controller.endpoints:
            action_name = endpoint.name if hasattr(endpoint, 'name') else str(endpoint)
            self._add_path_to_spec(module, ctrl_name, action_name, schema_name if model_schema else None)

    def _find_and_parse_model(self, vendor: str, module: str, controller_name: str) -> dict[str, Any] | None:
        """Locates the corresponding XML model and parses fields."""
        if not self.models_dir:
            return None

        # Try strict naming first: .../models/OPNsense/Firewall/Alias.xml
        xml_path = self.models_dir / vendor / module / f"{controller_name}.xml"

        # Fallback: sometimes the model is named after the module (e.g. .../Firewall.xml)
        if not xml_path.exists():
            xml_path = self.models_dir / vendor / module / f"{module}.xml"

        if xml_path.exists():
            return self._parse_xml_model(xml_path)
        return None

    def _parse_xml_model(self, xml_path: Path) -> dict[str, Any] | None:
        """Recursively parses OPNsense Model XML and resolves Enums."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            properties = {}

            for elem in root.iter():
                if 'type' in elem.attrib:
                    field_name = elem.tag
                    field_type = elem.attrib['type']
                    prop_def = TYPE_MAP.get(field_type, {"type": "string"}).copy()

                    # === ENUM RESOLUTION LOGIC ===
                    if field_type == "OptionField":
                        # 1. Check for Inline Options
                        inline_opts = elem.find('OptionValues')
                        if inline_opts is not None:
                            enums = [child.tag for child in inline_opts]
                            if enums:
                                prop_def['enum'] = enums

                        # 2. Check for External Source (<Source>OPNsense.Firewall.AliasTypes</Source>)
                        source_tag = elem.find('Source')
                        if source_tag is not None and source_tag.text:
                            enums = self._resolve_external_enums(source_tag.text)
                            if enums:
                                prop_def['enum'] = enums

                    properties[field_name] = prop_def

            return {"type": "object", "properties": properties}
        except Exception as e:
            logger.warning(f"Failed to parse model XML {xml_path}: {e}")
            return None

    def _resolve_external_enums(self, source_string: str) -> list[str]:
        """Resolves dot-notation sources to file paths to extract options."""
        if not self.models_dir:
            return []

        try:
            # e.g., OPNsense.Firewall.AliasTypes
            parts = source_string.split('.')
            if len(parts) < 3: return []

            # Path: models/OPNsense/Firewall/FieldTypes/AliasTypes.xml
            # We assume self.models_dir points to .../models/
            # Note: OPNsense structure usually puts shared types in a FieldTypes folder or root of module

            # Attempt 1: Inside FieldTypes subdirectory
            xml_path = self.models_dir / parts[0] / parts[1] / "FieldTypes" / f"{parts[-1]}.xml"

            # Attempt 2: Direct in module folder
            if not xml_path.exists():
                xml_path = self.models_dir / parts[0] / parts[1] / f"{parts[-1]}.xml"

            if xml_path.exists():
                tree = ET.parse(xml_path)
                root = tree.getroot()
                # Extract tag names (keys) or values depending on structure.
                # Usually in OPNsense FieldTypes, the children tags are the keys.
                return [child.tag for child in root]

        except Exception:
            pass
        return []

    def _create_search_schema(self, model_schema_name: str) -> None:
        """Creates a standardized pagination response for this model."""
        search_name = f"{model_schema_name}Search"
        self.spec['components']['schemas'][search_name] = {
            "type": "object",
            "properties": {
                "current": {"type": "integer", "example": 1},
                "rowCount": {"type": "integer", "example": 10},
                "total": {"type": "integer", "example": 50},
                "rows": {
                    "type": "array",
                    "items": {"$ref": f"#/components/schemas/{model_schema_name}"}
                }
            }
        }

    def _add_path_to_spec(self, module: str, controller: str, action: str, schema_name: str | None) -> None:
        """Constructs the OpenAPI Operation object with correct paths and parameters."""
        # Use CamelCase for action in URL (standard OPNsense routing)
        # But we check logic using lowercase
        act_lower = action.lower()

        # === UUID HEURISTIC ===
        # Detect if this endpoint likely acts on a specific resource ID
        target_verbs = ['get', 'set', 'del', 'toggle', 'start', 'stop', 'restart', 'kill', 'drop', 'disconnect', 'connect']
        target_nouns = ['item', 'rule', 'server', 'client', 'job', 'route', 'alias', 'certificate', 'ca', 'session', 'key', 'vessel']

        has_verb = any(v in act_lower for v in target_verbs)
        has_noun = any(n in act_lower for n in target_nouns)
        # Exempt list-based actions
        is_exception = any(e in act_lower for e in ['add', 'search', 'list', 'match', 'export', 'import', 'options'])

        requires_uuid = has_verb and has_noun and not is_exception

        # Build Path
        path_base = f"/api/{module.lower()}/{controller.lower()}/{action}"
        if requires_uuid:
            url = f"{path_base}/{{uuid}}"
            parameters = [{
                "name": "uuid",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
                "description": "Unique ID of the resource"
            }]
        else:
            url = path_base
            parameters = []

        # === RESPONSE/REQUEST LOGIC ===
        response_schema = {"description": "Successful response"}
        request_body = None

        if schema_name:
            # Search = Pagination
            if "search" in act_lower:
                response_schema["content"] = {
                    "application/json": {"schema": {"$ref": f"#/components/schemas/{schema_name}Search"}}
                }
            # Get = Single Object Wrapped
            elif "get" in act_lower:
                response_schema["content"] = {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                # OPNsense returns payload wrapped in controller name, usually lowercase
                                controller.lower(): {"$ref": f"#/components/schemas/{schema_name}"}
                            }
                        }
                    }
                }
            # Mutations = Status
            elif any(x in act_lower for x in ['add', 'set', 'del', 'toggle', 'update']):
                response_schema["content"] = {
                    "application/json": {"schema": {"$ref": "#/components/schemas/StatusResponse"}}
                }

            # Request Body for mutations
            if any(x in act_lower for x in ['add', 'set', 'update']):
                request_body = {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    controller.lower(): {"$ref": f"#/components/schemas/{schema_name}"}
                                }
                            }
                        }
                    }
                }

        # Add to spec
        self.spec['paths'][url] = {
            "post": {
                "tags": [module],
                "summary": action,
                "operationId": f"{module}_{controller}_{action}",
                "parameters": parameters,
                "requestBody": request_body,
                "responses": {
                    "200": response_schema
                }
            }
        }
