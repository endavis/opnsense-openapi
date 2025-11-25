"""OpenAPI Spec Validator against live OPNsense instance."""

import json
import logging
from pathlib import Path
from typing import Any, Generator

import httpx
import jsonschema
from jsonschema import ValidationError # Import ValidationError
from jsonschema.validators import validator_for

from opnsense_openapi.client import OPNsenseClient

logger = logging.getLogger(__name__)


class SpecValidator:
    """Validates OpenAPI spec against a live OPNsense instance."""

    def __init__(self, client: OPNsenseClient, spec_path: Path) -> None:
        """Initialize validator.

        Args:
            client: Authenticated OPNsense client
            spec_path: Path to the OpenAPI specification file
        """
        self.client = client
        self.spec_path = spec_path
        with spec_path.open() as f:
            self.spec = json.load(f)
        
        # Pre-resolve refs if needed, or rely on jsonschema's ref resolver
        # We'll rely on jsonschema's resolver with a base URI
        self.resolver = jsonschema.RefResolver(
            base_uri=f"file://{spec_path.absolute()}", 
            referrer=self.spec
        )

    def validate_endpoints(self, max_endpoints: int = 50) -> Generator[dict[str, Any], None, None]:
        """Crawl safe GET endpoints and validate responses.

        Args:
            max_endpoints: Maximum number of endpoints to test

        Yields:
            Dictionary with validation result for each endpoint
        """
        count = 0
        paths = self.spec.get("paths", {})

        for path, methods in paths.items():
            if count >= max_endpoints:
                break

            # Only check GET requests
            if "get" not in methods:
                continue

            # Skip paths with parameters (e.g. {uuid}) as we can't guess them
            if "{" in path:
                continue

            # Safety check: skip obviously dangerous paths just in case
            if any(x in path.lower() for x in ["reboot", "poweroff", "halt", "delete", "destroy"]):
                continue

            count += 1
            result = {
                "path": path,
                "method": "GET",
                "valid": False,
                "error": None,
                "status": 0
            }

            try:
                url = f"{self.client.base_url}{path}"
                response = self.client._client.get(url)
                result["status"] = response.status_code

                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "").lower()
                    
                    response_content_schema_block = methods["get"]["responses"]["200"].get("content")
                    
                    # Determine if the spec expects JSON content for 200 OK
                    spec_expects_json = response_content_schema_block and "application/json" in response_content_schema_block
                    
                    if spec_expects_json:
                        # Spec expects JSON, so validate accordingly
                        if "application/json" in content_type:
                            try:
                                data = response.json()
                                response_schema = response_content_schema_block["application/json"]["schema"]
                                
                                cls = validator_for(response_schema)
                                validator = cls(response_schema, resolver=self.resolver)
                                validator.validate(data)
                                
                                result["valid"] = True
                            except json.JSONDecodeError:
                                result["error"] = "Invalid JSON response (server returned malformed JSON despite Content-Type)"
                            except ValidationError as e:
                                result["error"] = f"Schema mismatch: {e.message} (at {'.'.join(str(p) for p in e.path)})"
                            except KeyError:
                                result["error"] = "Schema definition missing for application/json"
                        else:
                            # Schema expects JSON, but server returned non-JSON content-type
                            result["error"] = f"Content-Type mismatch: Server returned '{content_type}' but schema expected 'application/json'."
                    else:
                        # Spec does NOT explicitly expect JSON for 200 OK (e.g., it might expect text/csv, or no content)
                        # Assume valid if HTTP 200 OK, skip schema validation.
                        result["valid"] = True
                        result["error"] = f"Schema does not explicitly expect JSON for 200 OK. Server returned '{content_type}'. Skipped content validation."
                else:
                    result["error"] = f"HTTP {response.status_code}"

            except Exception as e:
                result["error"] = str(e)

            yield result
