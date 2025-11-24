"""Analyze PHP controller methods to infer response schemas."""

import re
from pathlib import Path
from typing import Any


class ResponseAnalyzer:
    """Infer response schemas from PHP controller method implementations."""

    # Known response schemas for ApiMutableModelControllerBase methods
    BASE_METHOD_SCHEMAS = {
        "searchBase": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Array of matching records",
                },
                "rowCount": {"type": "integer", "description": "Number of rows in current page"},
                "total": {"type": "integer", "description": "Total number of matching records"},
                "current": {"type": "integer", "description": "Current page number"},
            },
            "required": ["rows", "rowCount", "total", "current"],
        },
        "searchRecordsetBase": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Array of matching records",
                },
                "rowCount": {"type": "integer", "description": "Number of rows in current page"},
                "total": {"type": "integer", "description": "Total number of matching records"},
                "current": {"type": "integer", "description": "Current page number"},
            },
            "required": ["rows", "rowCount", "total", "current"],
        },
        "getBase": {
            "type": "object",
            "description": "Returns model data under a key matching the model name",
            "additionalProperties": True,
            # Note: The object has a single top-level key (model name) containing the model data
        },
        "setBase": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "enum": ["saved", "failed"],
                    "description": "Operation result",
                },
                "validations": {
                    "type": "object",
                    "description": "Validation errors if any",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["result"],
        },
        "addBase": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "enum": ["saved", "failed"],
                    "description": "Operation result",
                },
                "uuid": {"type": "string", "description": "UUID of created item"},
                "validations": {
                    "type": "object",
                    "description": "Validation errors if any",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["result"],
        },
        "delBase": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "enum": ["deleted", "failed", "not_found"],
                    "description": "Deletion result",
                },
            },
            "required": ["result"],
        },
        "toggleBase": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "enum": ["saved", "failed"],
                    "description": "Toggle operation result",
                },
                "changed": {"type": "boolean", "description": "Whether state was changed"},
            },
            "required": ["result"],
        },
        # Service control methods (ApiMutableServiceControllerBase)
        "startAction": {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "Service start response output",
                },
            },
            "required": ["response"],
        },
        "stopAction": {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "Service stop response output",
                },
            },
            "required": ["response"],
        },
        "restartAction": {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "Service restart response output",
                },
            },
            "required": ["response"],
        },
        "reconfigureAction": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ok", "failed"],
                    "description": "Reconfigure operation status",
                },
            },
            "required": ["status"],
        },
        "statusAction": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["running", "stopped", "disabled", "unknown"],
                    "description": "Service status",
                },
                "widget": {
                    "type": "object",
                    "properties": {
                        "caption_restart": {"type": "string"},
                        "caption_start": {"type": "string"},
                        "caption_stop": {"type": "string"},
                    },
                    "description": "Widget caption translations",
                },
            },
            "required": ["status"],
        },
    }

    def __init__(self) -> None:
        """Initialize response analyzer."""
        pass

    def infer_response_schema(
        self, php_file: Path, method_name: str, _depth: int = 0
    ) -> dict[str, Any] | None:
        """Infer response schema for a specific method.

        Args:
            php_file: Path to PHP controller file
            method_name: Name of the method (e.g., 'searchItemAction')
            _depth: Internal recursion depth tracker

        Returns:
            JSON Schema dict or None if cannot infer
        """
        # Check if this is a known inherited service action method
        # These are from ApiMutableServiceControllerBase and won't be in child controllers
        if method_name in self.BASE_METHOD_SCHEMAS:
            return self.BASE_METHOD_SCHEMAS[method_name].copy()

        try:
            content = php_file.read_text(encoding="utf-8")
        except Exception:
            return None

        # Extract method body
        method_body = self._extract_method_body(content, method_name)
        if not method_body:
            return None

        # Analyze return statements with access to full file content for method resolution
        return self._analyze_returns(method_body, content, _depth)

    def _extract_method_body(self, content: str, method_name: str) -> str | None:
        """Extract method body from PHP content.

        Args:
            content: PHP file content
            method_name: Method name to extract

        Returns:
            Method body or None if not found
        """
        # Find method start (public, private, or protected)
        pattern = rf"(?:public|private|protected)\s+function\s+{re.escape(method_name)}\s*\([^)]*\)\s*\{{"
        match = re.search(pattern, content)
        if not match:
            return None

        # Start after the opening brace
        start = match.end()

        # Count braces to find matching closing brace
        brace_count = 1
        i = start
        while i < len(content) and brace_count > 0:
            if content[i] == "{":
                brace_count += 1
            elif content[i] == "}":
                brace_count -= 1
            i += 1

        if brace_count == 0:
            # Found matching closing brace
            return content[start : i - 1]  # Exclude the closing brace

        return None

    def _analyze_returns(
        self, method_body: str, file_content: str, depth: int = 0, max_depth: int = 3
    ) -> dict[str, Any] | None:
        """Analyze return statements in method body.

        Args:
            method_body: PHP method body content
            file_content: Full PHP file content (for method resolution)
            depth: Current recursion depth
            max_depth: Maximum recursion depth for method resolution

        Returns:
            Inferred JSON Schema or None
        """
        # Find all return statements
        return_pattern = r"return\s+([^;]+);"
        returns = re.findall(return_pattern, method_body, re.DOTALL)

        if not returns:
            return None

        # Try to infer schema from each return statement
        # Then merge properties from all branches
        schemas = []

        for return_expr in returns:
            return_expr = return_expr.strip()
            original_return_expr = return_expr  # Keep original for plain array detection

            # Check if it's a variable - trace back to assignment
            if return_expr.startswith("$"):
                var_name = return_expr.split()[0]  # Get variable name (e.g., "$result")
                traced_expr = self._trace_variable(method_body, var_name)
                if traced_expr:
                    return_expr = traced_expr

            # Check for base method calls (these are definitive, return immediately)
            schema = self._match_base_method(return_expr)
            if schema:
                return schema

            # Check for method calls within same controller (before other patterns)
            if depth < max_depth:
                schema = self._resolve_method_call(return_expr, file_content, depth)
                if schema:
                    schemas.append(schema)
                    continue

            # Check for service action patterns
            schema = self._match_service_action(method_body, return_expr)
            if schema:
                schemas.append(schema)
                continue

            # Check for list/export array patterns using method body
            schema = self._detect_list_export_pattern(method_body, return_expr)
            if schema:
                schemas.append(schema)
                continue

            # Check for plain array patterns using original expression
            schema = self._match_plain_array(method_body, original_return_expr)
            if schema:
                schemas.append(schema)
                continue

            # Check for array literals
            schema = self._parse_array_literal(return_expr)
            if schema:
                schemas.append(schema)
                continue

            # Check for simple patterns
            schema = self._match_simple_patterns(return_expr)
            if schema:
                schemas.append(schema)
                continue

        # If we found multiple schemas, merge their properties
        if schemas:
            return self._merge_schemas(schemas)

        return None

    def _match_base_method(self, return_expr: str) -> dict[str, Any] | None:
        """Match return expression against known base methods.

        Args:
            return_expr: Return expression from PHP

        Returns:
            Known schema or None
        """
        # Check for $this->methodBase(...) calls
        for base_method, schema in self.BASE_METHOD_SCHEMAS.items():
            if f"$this->{base_method}(" in return_expr:
                return schema.copy()

        return None

    def _resolve_method_call(
        self, return_expr: str, file_content: str, depth: int
    ) -> dict[str, Any] | None:
        """Resolve method calls within the same controller.

        Args:
            return_expr: Return expression that may contain a method call
            file_content: Full PHP file content
            depth: Current recursion depth

        Returns:
            Resolved schema or None
        """
        # Check for $this->methodName(...) pattern
        method_call_pattern = r"\$this->(\w+)\s*\("
        match = re.search(method_call_pattern, return_expr)

        if not match:
            return None

        called_method = match.group(1)

        # Extract and analyze the called method
        called_method_body = self._extract_method_body(file_content, called_method)
        if not called_method_body:
            return None

        # Recursively analyze the called method
        return self._analyze_returns(called_method_body, file_content, depth + 1)


    def _match_service_action(self, method_body: str, return_expr: str) -> dict[str, Any] | None:
        """Match service control action patterns.

        Args:
            method_body: Full method body (to check for Backend calls)
            return_expr: Return expression from PHP

        Returns:
            Service action schema or None
        """
        # Check if method uses Backend()->configdRun or configdpRun
        has_backend_call = (
            "Backend()" in method_body
            and ("configdRun" in method_body or "configdpRun" in method_body)
        )

        if not has_backend_call:
            return None

        # Check if return contains status or result with typical service values
        # Pattern: ['status' => 'ok'], ['result' => 'failed'], etc.
        if ('"status"' in return_expr or "'status'" in return_expr) and (
            '"ok"' in return_expr
            or "'ok'" in return_expr
            or '"failed"' in return_expr
            or "'failed'" in return_expr
        ):
            return {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["ok", "failed"],
                        "description": "Service action status",
                    }
                },
                "required": ["status"],
            }

        if ('"result"' in return_expr or "'result'" in return_expr) and (
            '"ok"' in return_expr
            or "'ok'" in return_expr
            or '"failed"' in return_expr
            or "'failed'" in return_expr
        ):
            return {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "enum": ["ok", "failed"],
                        "description": "Service action result",
                    }
                },
                "required": ["result"],
            }

        return None

    def _detect_list_export_pattern(
        self, method_body: str, return_expr: str
    ) -> dict[str, Any] | None:
        """Detect list/export patterns that return simple arrays.

        Args:
            method_body: Full method body
            return_expr: Return expression from PHP (may be traced expression)

        Returns:
            Array schema or None
        """
        # Pattern 1: Check if return expression itself is a json_decode call (after tracing)
        if "json_decode" in return_expr:
            # json_decode typically returns arrays for list/export endpoints
            return {
                "type": "array",
                "items": {"type": "object"},
                "description": "Array of items",
            }

        # Pattern 2: Check if return expression is an empty array literal (after tracing)
        # This means a variable was traced back to [] or array()
        if return_expr.strip() in ("[]", "array()"):
            # Find variables initialized as empty arrays
            # Look for $var = []; or $var = array();
            var_init_pattern = r"(\$\w+)\s*=\s*(?:\[\s*\]|array\(\s*\))\s*;"
            var_matches = re.findall(var_init_pattern, method_body)

            for var_name in var_matches:
                # Check if this variable has items added to it
                build_patterns = [
                    rf"{re.escape(var_name)}\[\s*[^\]]*\s*\]\s*=",  # $var['key'] = or $var[$key] =
                    rf"array_push\s*\(\s*{re.escape(var_name)}",  # array_push($var, ...)
                ]

                if any(re.search(pat, method_body) for pat in build_patterns):
                    # This is an associative array being built up
                    return {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Object with dynamic keys",
                    }

        # Pattern 3: Check if return expr is a variable and trace back to json_decode
        if return_expr.startswith("$"):
            var_match = re.match(r"(\$\w+)", return_expr)
            if not var_match:
                return None

            var_name = var_match.group(1)

            # Check for json_decode assignment
            # e.g., $result = json_decode(...);
            json_decode_pattern = rf"{re.escape(var_name)}\s*=\s*json_decode\s*\("
            if re.search(json_decode_pattern, method_body):
                # json_decode typically returns arrays for list/export endpoints
                return {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Array of items",
                }

            # Pattern 4: Check for variable initialized as empty array and items added (when not traced)
            # Look for both $var = []; pattern and items being added
            init_patterns = [
                rf"{re.escape(var_name)}\s*=\s*\[\s*\];",  # $result = [];
                rf"{re.escape(var_name)}\s*=\s*array\(\s*\);",  # $result = array();
            ]

            is_initialized_empty = any(re.search(pat, method_body) for pat in init_patterns)

            # Look for array building patterns
            build_patterns = [
                rf"{re.escape(var_name)}\[\s*[^\]]*\s*\]\s*=",  # $result['key'] = or $result[$key] =
                rf"array_push\s*\(\s*{re.escape(var_name)}",  # array_push($result, ...)
            ]

            is_array_built = any(re.search(pat, method_body) for pat in build_patterns)

            if is_initialized_empty and is_array_built:
                # This is an array being built up
                # Check if it looks like an associative array (has string keys) or indexed array
                # Most list endpoints return arrays of objects (associative)
                return {
                    "type": "object",
                    "additionalProperties": True,
                    "description": "Object with dynamic keys",
                }

        # Pattern 5: Check for "rows" wrapper pattern
        # return ['rows' => $data];
        if '"rows"' in return_expr or "'rows'" in return_expr:
            return {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Array of items",
                    }
                },
            }

        return None

    def _match_plain_array(self, method_body: str, return_expr: str) -> dict[str, Any] | None:
        """Match plain array construction patterns.

        Args:
            method_body: Full method body (to check for array building)
            return_expr: Return expression from PHP

        Returns:
            Plain array schema or None
        """
        # Check if return expr is a simple variable
        if not return_expr.startswith("$"):
            return None

        # Extract variable name
        var_match = re.match(r"(\$\w+)", return_expr)
        if not var_match:
            return None

        var_name = var_match.group(1)

        # Look for patterns that indicate this is a plain array:
        # 1. $var = [];
        # 2. $var[] = ...;
        # 3. array_push($var, ...);
        patterns = [
            rf"{re.escape(var_name)}\s*=\s*\[\s*\];",  # $result = [];
            rf"{re.escape(var_name)}\s*=\s*array\(\s*\);",  # $result = array();
            rf"{re.escape(var_name)}\[\s*\]\s*=",  # $result[] = ...;
            rf"array_push\s*\(\s*{re.escape(var_name)}",  # array_push($result, ...);
        ]

        for pattern in patterns:
            if re.search(pattern, method_body):
                return {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of items",
                }

        return None

    def _parse_array_literal(self, return_expr: str) -> dict[str, Any] | None:
        """Parse PHP array literal into JSON schema.

        Args:
            return_expr: Return expression (should be array literal)

        Returns:
            JSON Schema or None
        """
        # Simple check: starts with [ or array(
        if not (return_expr.startswith("[") or return_expr.startswith("array(")):
            return None

        properties = {}

        # Extract key-value pairs using a more robust approach
        # This handles nested arrays and multi-line formatting
        properties = self._extract_array_properties(return_expr)

        if properties:
            return {"type": "object", "properties": properties}

        return None

    def _extract_array_properties(self, array_str: str) -> dict[str, dict[str, Any]]:
        """Extract properties from array literal using bracket counting.

        Args:
            array_str: PHP array literal string

        Returns:
            Dictionary mapping property names to their schemas
        """
        properties = {}

        # Remove outer brackets/array() wrapper
        array_str = array_str.strip()
        if array_str.startswith("array("):
            array_str = array_str[6:-1]  # Remove "array(" and ")"
        elif array_str.startswith("["):
            array_str = array_str[1:-1]  # Remove "[" and "]"

        # Find all key => value pairs
        i = 0
        while i < len(array_str):
            # Look for quoted key
            key_match = re.match(r'\s*["\'](\w+)["\']\s*=>\s*', array_str[i:])
            if not key_match:
                i += 1
                continue

            key = key_match.group(1)
            i += key_match.end()

            # Extract the value (may be nested array or simple value)
            value_str, value_end = self._extract_value(array_str, i)
            if value_str:
                schema = self._infer_value_type(value_str.strip())
                properties[key] = schema

            i += value_end

        return properties

    def _extract_value(self, text: str, start: int) -> tuple[str, int]:
        """Extract a value from array literal, handling nested structures.

        Args:
            text: Text to extract from
            start: Starting position

        Returns:
            Tuple of (extracted_value, length_consumed)
        """
        i = start
        # Skip whitespace
        while i < len(text) and text[i].isspace():
            i += 1

        if i >= len(text):
            return "", 0

        # Check if value is a nested array
        if text[i] in "[":
            bracket_count = 1
            value_start = i
            i += 1
            while i < len(text) and bracket_count > 0:
                if text[i] == "[":
                    bracket_count += 1
                elif text[i] == "]":
                    bracket_count -= 1
                i += 1
            return text[value_start:i], i - start

        # Check if value is array() syntax
        if text[i:].startswith("array("):
            paren_count = 1
            value_start = i
            i += 6  # Skip "array("
            while i < len(text) and paren_count > 0:
                if text[i] == "(":
                    paren_count += 1
                elif text[i] == ")":
                    paren_count -= 1
                i += 1
            return text[value_start:i], i - start

        # Simple value - read until comma or closing bracket
        value_start = i
        while i < len(text) and text[i] not in ",])\n":
            i += 1

        return text[value_start:i].strip(), i - start

    def _infer_value_type(self, value: str) -> dict[str, Any]:
        """Infer JSON schema type from PHP value expression.

        Args:
            value: PHP value expression (e.g., "42", "true", "'string'", "[]")

        Returns:
            JSON Schema for the value
        """
        value = value.strip()

        # Boolean literals
        if value in ("true", "false"):
            return {"type": "boolean"}

        # Null literal
        if value == "null":
            return {"type": "null"}

        # Integer literals (simple numeric pattern)
        if re.match(r"^-?\d+$", value):
            return {"type": "integer"}

        # Float literals
        if re.match(r"^-?\d+\.\d+$", value):
            return {"type": "number"}

        # Array literals
        if value.startswith("[") or value.startswith("array("):
            # Could be array of objects or simple array
            return {"type": "array", "items": {"type": "object"}}

        # String literals (quoted)
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return {"type": "string"}

        # Variable or expression - default to string
        return {"type": "string"}

    def _match_simple_patterns(self, return_expr: str) -> dict[str, Any] | None:
        """Match simple return patterns.

        Args:
            return_expr: Return expression

        Returns:
            JSON Schema or None
        """
        # Check for common status response pattern
        if '"status"' in return_expr or "'status'" in return_expr:
            return {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Operation status"},
                },
            }

        # Check for result pattern
        if '"result"' in return_expr or "'result'" in return_expr:
            return {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "description": "Operation result"},
                },
            }

        return None

    def _merge_schemas(self, schemas: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge multiple schemas into a single schema with all properties.

        Args:
            schemas: List of JSON Schema objects to merge

        Returns:
            Merged JSON Schema
        """
        if not schemas:
            return {"type": "object"}

        if len(schemas) == 1:
            return schemas[0]

        # Merge all properties from all schemas
        merged_properties = {}
        merged_required = set()

        for schema in schemas:
            if schema.get("type") != "object":
                continue

            props = schema.get("properties", {})
            for prop_name, prop_schema in props.items():
                if prop_name in merged_properties:
                    # Property exists - try to merge its type/enum
                    existing = merged_properties[prop_name]
                    merged_properties[prop_name] = self._merge_property_schemas(
                        existing, prop_schema
                    )
                else:
                    merged_properties[prop_name] = prop_schema.copy()

            # A property is required only if it appears in ALL schemas
            required = set(schema.get("required", []))
            if not merged_required:
                merged_required = required
            else:
                merged_required &= required

        result = {"type": "object", "properties": merged_properties}
        if merged_required:
            result["required"] = sorted(merged_required)

        return result

    def _merge_property_schemas(
        self, schema1: dict[str, Any], schema2: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge two property schemas for the same property name.

        Args:
            schema1: First property schema
            schema2: Second property schema

        Returns:
            Merged property schema
        """
        # If they're the same type, merge enums if present
        if schema1.get("type") == schema2.get("type"):
            merged = schema1.copy()

            # Merge enum values
            enum1 = set(schema1.get("enum", []))
            enum2 = set(schema2.get("enum", []))
            if enum1 or enum2:
                merged["enum"] = sorted(enum1 | enum2)

            # Prefer more descriptive description
            if not merged.get("description") and schema2.get("description"):
                merged["description"] = schema2["description"]

            return merged

        # Different types - return a union-like schema (just use string as fallback)
        return {"type": "string"}

    def _trace_variable(
        self, method_body: str, var_name: str, depth: int = 0, max_depth: int = 5
    ) -> str | None:
        """Trace a variable back to its assignment recursively.

        Args:
            method_body: Method body content
            var_name: Variable name (e.g., "$result")
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops

        Returns:
            Assignment expression or None
        """
        if depth >= max_depth:
            return None

        # Look for $varname = expression;
        # Pattern: $varname = ... (up to semicolon)
        pattern = rf"{re.escape(var_name)}\s*=\s*([^;]+);"
        matches = re.findall(pattern, method_body, re.DOTALL)

        if not matches:
            return None

        # Get the last assignment (most recent)
        assignment = matches[-1].strip()

        # If the assignment is another variable, trace it recursively
        # Handle both simple assignment ($a = $b) and with method calls ($a = $b->foo())
        if assignment.startswith("$"):
            # Extract just the variable name (first token)
            next_var = assignment.split()[0]
            # Remove any trailing operators or method calls
            next_var = re.match(r"(\$\w+)", next_var)
            if next_var:
                next_var = next_var.group(1)
                # Recursively trace this variable
                traced = self._trace_variable(method_body, next_var, depth + 1, max_depth)
                if traced:
                    return traced

        return assignment
