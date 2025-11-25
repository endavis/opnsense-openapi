"""Generate OpenAPI JSON specification from parsed API controllers."""

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..parser import ApiController

logger = logging.getLogger(__name__)

def _get_xml_tag_text(elem: ET.Element, tag_name: str) -> str | None:
    """Safely extract text from a child XML element."""
    child = elem.find(tag_name)
    return child.text if child is not None else None

# ================= TYPE MAPPING =================
TYPE_MAP = {
    "IntegerField": {"type": "integer"},
    "TextField": {"type": "string"},
    "BooleanField": {"type": "string", "enum": ["0", "1"], "description": "Boolean (0=false, 1=true)"},
    "NetworkField": {"type": "string", "format": "ipv4"},
    "OptionField": {"type": "string", "description": "Dropdown selection"}, # Reverted to string default
    "ModelRelationField": {"type": "string", "description": "UUID reference"},
    "CSVListField": {"type": "string", "description": "Comma separated values"},
    "CertificateField": {"type": "string", "description": "Certificate Data"},
    "EmailField": {"type": "string", "format": "email"},
    "ArrayField": {"type": "array", "items": {"type": "object"}},
    "InterfaceField": {
        "type": "object",
        "additionalProperties": {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
                "selected": {"type": "integer"}
            }
        },
        "description": "Interface selection. Keys are Interface IDs (e.g., 'lan', 'wan', 'opt1'). Returns a map of interfaces on read, expects a comma-separated string of Interface IDs on write.",
        "example": {
            "lan": {"value": "LAN", "selected": 0},
            "wan": {"value": "WAN", "selected": 1}
        }
    },
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
    ) -> Path:
        """Generate OpenAPI specification for all controllers.

        Args:
            controllers: List of parsed API controllers
            version: OPNsense version
            models_dir: Directory containing model XML files

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

        # Determine response wrapper name
        # Priority: 1. $internalModelName from controller (if parsed)
        #           2. Controller name (lowercase)
        response_wrapper = controller.model_name if controller.model_name else ctrl_name.lower()

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
            http_method = endpoint.method if hasattr(endpoint, 'method') else "POST"
            description = endpoint.description if hasattr(endpoint, 'description') else ""
            self._add_path_to_spec(
                module, 
                ctrl_name, 
                action_name, 
                schema_name if model_schema else None, 
                http_method, 
                description,
                response_wrapper
            )

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
            # Start parsing from the root's items
            items_node = root.find('items')
            if items_node is None:
                # Fallback: try iterating root children if no <items> tag (unlikely for OPNsense models)
                properties = self._parse_model_nodes(root)
            else:
                properties = self._parse_model_nodes(items_node)

            return {"type": "object", "properties": properties}
        except Exception as e:
            logger.warning(f"Failed to parse model XML {xml_path}: {e}")
            return None

    def _parse_model_nodes(self, parent_node: ET.Element) -> dict[str, Any]:
        """Recursively parse XML nodes to build property definitions."""
        properties = {}
        for elem in parent_node:
            field_name = elem.tag
            # Skip comments or odd tags
            if not isinstance(field_name, str):
                continue

            if 'type' in elem.attrib:
                field_type = elem.attrib['type']
                # Strip relative path chars from type (e.g. ".\HostnameField")
                clean_type = field_type.lstrip(".\\/")
                
                prop_def = TYPE_MAP.get(clean_type, {"type": "string"}).copy()

                # === ARRAY FIELD HANDLING ===
                if clean_type == "ArrayField":
                    # Recurse into children to find the item structure
                    # ArrayField children define the properties of the objects in the array
                    child_props = self._parse_model_nodes(elem)
                    if child_props:
                        prop_def['items'] = {
                            "type": "object",
                            "properties": child_props
                        }
                    else:
                        # Fallback if no children defined
                        prop_def['items'] = {"type": "object", "additionalProperties": True}

                # === ENUM RESOLUTION LOGIC ===
                elif clean_type == "OptionField":
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
            
            else:
                # No type attribute - check if it's a container (has children)
                # recursing if it has children that look like fields
                if len(elem) > 0:
                    # Check if it's a container node (like 'dhcp' in Dnsmasq)
                    child_props = self._parse_model_nodes(elem)
                    if child_props:
                        properties[field_name] = {
                            "type": "object",
                            "properties": child_props
                        }
        
        return properties

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

    def _add_path_to_spec(self, module: str, controller: str, action: str, schema_name: str | None, http_method: str = "POST", description: str = "", response_wrapper: str | None = None) -> None:
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

        # === SERVICE ACTION PATTERNS (from ApiMutableServiceControllerBase) ===
        # These take priority - check first before other patterns
        if any(x in act_lower for x in ['start', 'stop', 'restart']):
            # start/stop/restart return {"response": "command output"}
            response_schema["content"] = {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "response": {"type": "string", "description": "Service command output"}
                        },
                        "required": ["response"]
                    }
                }
            }
        elif 'reconfigure' in act_lower:
            # reconfigure returns {"status": "ok"|"failed"}
            response_schema["content"] = {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["ok", "failed"], "description": "Reconfigure status"}
                        },
                        "required": ["status"]
                    }
                }
            }
        elif 'status' in act_lower:
            # status returns {"status": "running"|"stopped"|...}
            # For some basic status endpoints (e.g., system/status), it might return {} if status is unknown/unavailable.
            # Make 'status' optional in these cases, unless 'widget' is also part of the response (rich status).
            is_rich_status = "widget" in action # Heuristic: if action name includes "widget", assume rich status
            required_status_property = ["status"] if is_rich_status else []
            
            response_schema["content"] = {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": ["running", "stopped", "disabled", "unknown", "failed", "update", "done", "ok", "inactive", "error", "not found"], # Expanded values
                            },
                            "widget": {"type": "object", "description": "UI widget captions"}
                        },
                        "required": required_status_property
                    }
                }
            }
        # === ARRAY RESPONSE PATTERNS (for lists of generic items) ===
        # Heuristic for endpoints that return an array of objects like getArp, getNdp, getLog, etc.
        elif http_method == "GET" and any(pattern in act_lower for pattern in ["arp", "ndp", "log", "leases", "sessions", "states", "routes"]):
            response_schema["content"] = {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "Dynamic object representing an item in the list"
                        },
                        "description": "List of dynamic items"
                    }
                }
            }
        # === BOOLEAN QUERY PATTERNS ===
        elif 'isenabled' in act_lower.replace('_', ''):
            # isEnabled returns {"enabled": "0"|"1"}
            response_schema["content"] = {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "enabled": {
                                "type": "string",
                                "enum": ["0", "1"],
                                "description": "Whether feature is enabled (0=false, 1=true)"
                            }
                        }
                    }
                }
            }
        # === STATISTICS/INFO PATTERNS ===
        elif any(x in act_lower for x in ['stats', 'info', 'overview', 'summary']):
            # Stats/info endpoints return objects with dynamic structure
            response_schema["content"] = {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Statistics or information object"
                    }
                }
            }
        # === SPECIAL OPERATIONS ===
        elif any(x in act_lower for x in ['apply', 'flush', 'revert', 'savepoint', 'rollback', 'upload', 'generate', 'kill', 'disconnect', 'connect']):
            # Operations that modify state and return status
            response_schema["content"] = {
                "application/json": {"schema": {"$ref": "#/components/schemas/StatusResponse"}}
            }
        # === QUERY/EXPORT PATTERNS ===
        elif any(x in act_lower for x in ['export', 'download', 'rawdump', 'dump', 'providers', 'accounts', 'templates']):
            # Export/download return data or file content
            response_schema["content"] = {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Export data or file content"
                    }
                }
            }
        # === LIST PATTERNS ===
        elif any(x in act_lower for x in ['list', 'aliases', 'countries', 'groups', 'users', 'categories']):
            # Check if 'list' might be paginated (listAction often calls searchRecordsetBase)
            if act_lower == 'list' and schema_name:
                # Paginated list response
                response_schema["content"] = {
                    "application/json": {"schema": {"$ref": f"#/components/schemas/{schema_name}Search"}}
                }
            else:
                # Simple array or object with dynamic keys
                response_schema["content"] = {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "Object with dynamic keys or array of items"
                        }
                    }
                }
        # === STANDARD MODEL-BASED PATTERNS ===
        elif schema_name:
            # Search/Find = Pagination (including Item variations like searchItem)
            if any(x in act_lower for x in ['search', 'find']) or act_lower.endswith('item'):
                response_schema["content"] = {
                    "application/json": {"schema": {"$ref": f"#/components/schemas/{schema_name}Search"}}
                }
            # Get = Single Object Wrapped
            elif "get" in act_lower:
                # Use custom wrapper (e.g. 'dnsmasq') if provided, otherwise controller name
                wrapper_name = response_wrapper if response_wrapper else controller.lower()
                response_schema["content"] = {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                # OPNsense returns payload wrapped in controller name or model name
                                wrapper_name: {"$ref": f"#/components/schemas/{schema_name}"}
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
        # === FALLBACK PATTERNS (no model found) ===
        else:
            # No model schema, but provide generic schemas for common patterns
            if any(x in act_lower for x in ['search', 'find']) or act_lower.endswith('item'):
                # Generic paginated response
                response_schema["content"] = {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "current": {"type": "integer"},
                                "rowCount": {"type": "integer"},
                                "total": {"type": "integer"},
                                "rows": {"type": "array", "items": {"type": "object"}}
                            }
                        }
                    }
                }
            elif "get" in act_lower:
                # Generic get response
                response_schema["content"] = {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "Resource data"
                        }
                    }
                }
            elif any(x in act_lower for x in ['add', 'set', 'update', 'delete', 'remove', 'del', 'toggle']):
                # Mutation operations return status
                response_schema["content"] = {
                    "application/json": {"schema": {"$ref": "#/components/schemas/StatusResponse"}}
                }

            # Request body for mutations without models
            if any(x in act_lower for x in ['add', 'set', 'update']):
                request_body = {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "additionalProperties": True,
                                "description": "Request payload"
                            }
                        }
                    }
                }

        # Add to spec
        method_key = http_method.lower()
        
        # GET requests should not have a body
        if method_key == 'get':
            request_body = None

        self.spec['paths'][url] = {
            method_key: {
                "tags": [module],
                "summary": action,
                "description": description if description else action,
                "operationId": f"{module}_{controller}_{action}",
                "parameters": parameters,
                "requestBody": request_body,
                "responses": {
                    "200": response_schema
                }
            }
        }
