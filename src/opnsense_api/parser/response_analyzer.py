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
        "getBase": {
            "type": "object",
            "description": "Returns model data under a key matching the model name",
            # Note: Actual structure depends on the model, but always has one top-level key
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
    }

    def __init__(self) -> None:
        """Initialize response analyzer."""
        pass

    def infer_response_schema(self, php_file: Path, method_name: str) -> dict[str, Any] | None:
        """Infer response schema for a specific method.

        Args:
            php_file: Path to PHP controller file
            method_name: Name of the method (e.g., 'searchItemAction')

        Returns:
            JSON Schema dict or None if cannot infer
        """
        try:
            content = php_file.read_text(encoding="utf-8")
        except Exception:
            return None

        # Extract method body
        method_body = self._extract_method_body(content, method_name)
        if not method_body:
            return None

        # Analyze return statements
        return self._analyze_returns(method_body)

    def _extract_method_body(self, content: str, method_name: str) -> str | None:
        """Extract method body from PHP content.

        Args:
            content: PHP file content
            method_name: Method name to extract

        Returns:
            Method body or None if not found
        """
        # Find method start
        pattern = rf"public\s+function\s+{re.escape(method_name)}\s*\([^)]*\)\s*\{{"
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

    def _analyze_returns(self, method_body: str) -> dict[str, Any] | None:
        """Analyze return statements in method body.

        Args:
            method_body: PHP method body content

        Returns:
            Inferred JSON Schema or None
        """
        # Find all return statements
        return_pattern = r"return\s+([^;]+);"
        returns = re.findall(return_pattern, method_body, re.DOTALL)

        if not returns:
            return None

        # Analyze the most complex return (usually the success path)
        # Sort by length to get the most detailed one
        returns.sort(key=len, reverse=True)

        for return_expr in returns:
            return_expr = return_expr.strip()

            # Check if it's a variable - trace back to assignment
            if return_expr.startswith("$"):
                var_name = return_expr.split()[0]  # Get variable name (e.g., "$result")
                traced_expr = self._trace_variable(method_body, var_name)
                if traced_expr:
                    return_expr = traced_expr

            # Check for base method calls
            schema = self._match_base_method(return_expr)
            if schema:
                return schema

            # Check for service action patterns (before generic array literal parsing)
            schema = self._match_service_action(method_body, return_expr)
            if schema:
                return schema

            # Check for array literals
            schema = self._parse_array_literal(return_expr)
            if schema:
                return schema

            # Check for simple patterns
            schema = self._match_simple_patterns(return_expr)
            if schema:
                return schema

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

        # Extract key-value pairs
        # Pattern: "key" => value or 'key' => value
        properties = {}

        # Find all quoted keys with their values
        # Match: "key" => value, up to comma or end of array
        key_value_pattern = r'["\'](\w+)["\']\s*=>\s*([^,\]\)]+)'
        matches = re.findall(key_value_pattern, return_expr)

        for key, value in matches:
            value = value.strip()

            # Infer type from value
            schema = self._infer_value_type(value)
            properties[key] = schema

        if properties:
            return {"type": "object", "properties": properties}

        return None

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

    def _trace_variable(self, method_body: str, var_name: str) -> str | None:
        """Trace a variable back to its assignment.

        Args:
            method_body: Method body content
            var_name: Variable name (e.g., "$result")

        Returns:
            Assignment expression or None
        """
        # Look for $varname = expression;
        # Pattern: $varname = ... (up to semicolon)
        pattern = rf"{re.escape(var_name)}\s*=\s*([^;]+);"
        matches = re.findall(pattern, method_body, re.DOTALL)

        if matches:
            # Return the last assignment (most recent)
            return matches[-1].strip()

        return None
