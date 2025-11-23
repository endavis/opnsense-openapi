"""Parse OPNsense model XML files to extract field definitions."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ModelField:
    """Represents a field in an OPNsense model."""

    name: str
    field_type: str  # e.g., BooleanField, TextField, OptionField
    required: bool = False
    default: str | None = None
    options: dict[str, str] = field(default_factory=dict)  # For OptionField
    multiple: bool = False


@dataclass
class ModelDefinition:
    """Represents an OPNsense model definition."""

    name: str  # e.g., "Alias"
    module: str  # e.g., "Firewall"
    mount: str  # e.g., "//OPNsense/Firewall/Alias"
    description: str
    fields: dict[str, list[ModelField]]  # container_name -> fields


class ModelParser:
    """Parser for OPNsense model XML files."""

    # Map OPNsense field types to JSON Schema types
    FIELD_TYPE_MAP = {
        "BooleanField": "boolean",
        "IntegerField": "integer",
        "NumericField": "number",
        "TextField": "string",
        "DescriptionField": "string",
        "EmailField": "string",
        "HostnameField": "string",
        "NetworkField": "string",
        "PortField": "string",
        "UrlField": "string",
        "OptionField": "string",
        "CSVListField": "string",
        "InterfaceField": "string",
        "ModelRelationField": "string",
        "UniqueIdField": "string",
        "CertificateField": "string",
        "AuthGroupField": "string",
        "AuthenticationServerField": "string",
    }

    def parse_model_file(self, file_path: Path) -> ModelDefinition | None:
        """Parse a model XML file.

        Args:
            file_path: Path to the XML file

        Returns:
            ModelDefinition or None if parsing fails
        """
        if not file_path.exists() or not file_path.suffix == ".xml":
            return None

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            logger.warning("Failed to parse XML file %s: %s", file_path, e)
            return None

        if root.tag != "model":
            return None

        mount = self._get_text(root, "mount", "")
        description = self._get_text(root, "description", "")

        # Extract module and name from file path
        # e.g., models/OPNsense/Firewall/Alias.xml -> module=Firewall, name=Alias
        module = file_path.parent.name
        name = file_path.stem

        fields: dict[str, list[ModelField]] = {}
        items = root.find("items")
        if items is not None:
            self._parse_items(items, fields, "")

        return ModelDefinition(
            name=name,
            module=module,
            mount=mount,
            description=description,
            fields=fields,
        )

    def _parse_items(
        self, element: ET.Element, fields: dict[str, list[ModelField]], prefix: str
    ) -> None:
        """Recursively parse items/containers.

        Args:
            element: XML element to parse
            fields: Dictionary to populate with fields
            prefix: Current path prefix
        """
        for child in element:
            field_type = child.get("type", "")
            child_name = child.tag

            if field_type:
                # This is a field definition
                container = prefix or "root"
                if container not in fields:
                    fields[container] = []

                model_field = self._parse_field(child, child_name, field_type)
                fields[container].append(model_field)

                # Check if this field is a container with nested fields
                if len(child) > 0:
                    new_prefix = f"{prefix}.{child_name}" if prefix else child_name
                    self._parse_items(child, fields, new_prefix)
            else:
                # This is a container, recurse into it
                new_prefix = f"{prefix}.{child_name}" if prefix else child_name
                self._parse_items(child, fields, new_prefix)

    def _parse_field(self, element: ET.Element, name: str, field_type: str) -> ModelField:
        """Parse a single field element.

        Args:
            element: XML field element
            name: Field name
            field_type: Field type string

        Returns:
            ModelField object
        """
        # Clean up field type (remove namespace prefix)
        clean_type = field_type.lstrip(".\\/")
        if not any(clean_type.endswith(ft) for ft in self.FIELD_TYPE_MAP):
            # Try to find a matching type
            for ft in self.FIELD_TYPE_MAP:
                if ft in clean_type:
                    clean_type = ft
                    break

        required = self._get_text(element, "Required", "N").upper() == "Y"
        default = self._get_text(element, "Default", None)
        multiple = self._get_text(element, "Multiple", "N").upper() == "Y"

        options = {}
        option_values = element.find("OptionValues")
        if option_values is not None:
            for opt in option_values:
                options[opt.tag] = opt.text or opt.tag

        return ModelField(
            name=name,
            field_type=clean_type,
            required=required,
            default=default,
            options=options,
            multiple=multiple,
        )

    def _get_text(self, element: ET.Element, tag: str, default: str | None) -> str | None:
        """Get text content of a child element.

        Args:
            element: Parent element
            tag: Child tag name
            default: Default value if not found

        Returns:
            Text content or default
        """
        child = element.find(tag)
        if child is not None and child.text:
            return child.text
        return default

    def to_json_schema(self, model: ModelDefinition, container: str = "root") -> dict:
        """Convert model fields to JSON Schema.

        Args:
            model: Model definition
            container: Container name to generate schema for

        Returns:
            JSON Schema dictionary
        """
        if container not in model.fields:
            return {"type": "object"}

        properties = {}
        required = []

        for model_field in model.fields[container]:
            json_type = self.FIELD_TYPE_MAP.get(model_field.field_type, "string")

            prop: dict = {"type": json_type}

            # Handle enum fields
            if model_field.options:
                enum_values = list(model_field.options.keys())

                # If there's a default value, ensure it's in the enum
                if model_field.default is not None and model_field.default not in enum_values:
                    # Add default to enum values if not already present
                    enum_values.append(model_field.default)

                prop["enum"] = enum_values

            # Convert default value to proper JSON type
            if model_field.default is not None:
                prop["default"] = self._convert_default_value(
                    model_field.default, json_type
                )

            if model_field.multiple:
                prop = {"type": "array", "items": prop}

            properties[model_field.name] = prop

            if model_field.required:
                required.append(model_field.name)

        schema: dict = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required

        return schema

    def _convert_default_value(self, default_str: str, json_type: str) -> str | int | float | bool:
        """Convert default value string to proper JSON type.

        Args:
            default_str: Default value as string from XML
            json_type: Target JSON type

        Returns:
            Converted value with proper type
        """
        if json_type == "boolean":
            # Convert "0"/"1" or "Y"/"N" to boolean
            return default_str.lower() in ("1", "y", "yes", "true")
        elif json_type == "integer":
            try:
                return int(default_str)
            except ValueError:
                return default_str
        elif json_type == "number":
            try:
                return float(default_str)
            except ValueError:
                return default_str
        else:
            # String type - return as-is
            return default_str

    def parse_directory(self, directory: Path) -> dict[str, ModelDefinition]:
        """Parse all model XML files in a directory.

        Args:
            directory: Directory containing model files

        Returns:
            Dictionary mapping model class name to definition
        """
        models = {}

        if not directory.exists():
            return models

        for xml_file in directory.rglob("*.xml"):
            # Skip Menu, Migrations, ACL directories
            if any(skip in xml_file.parts for skip in ["Menu", "Migrations", "ACL"]):
                continue

            model = self.parse_model_file(xml_file)
            if model:
                # Key format: OPNsense\Module\Name
                key = f"OPNsense\\{model.module}\\{model.name}"
                models[key] = model

        return models
