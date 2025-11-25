"""OpenAPI Spec Validator against live OPNsense instance."""

import json
import logging
from pathlib import Path
from typing import Any, Generator

import httpx
import jsonschema
from jsonschema.validators import validator_for

from opnsense_api.client import OPNsenseClient

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
                # Construct API URL
                # The path in spec is like /api/core/firmware/info
                # Client expects module, controller, command
                # But client.get() constructs from parts. 
                # We can use the underlying client to fetch the full path directly
                # correcting for the client's base_url
                
                # path already contains /api prefix usually in our generation
                # e.g. /api/core/firmware/info
                # client.base_url is https://host
                
                url = f"{self.client.base_url}{path}"
                
                response = self.client._client.get(url)
                result["status"] = response.status_code

                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # Get response schema
                        response_schema = methods["get"]["responses"]["200"]["content"]["application/json"]["schema"]
                        
                        # Validate
                        # We need to prepare the validator with the resolver
                        cls = validator_for(response_schema)
                        validator = cls(response_schema, resolver=self.resolver)
                        validator.validate(data)
                        
                        result["valid"] = True
                    except jsonschema.ValidationError as e:
                        result["error"] = f"Schema mismatch: {e.message} (at {e.path})"
                    except json.JSONDecodeError:
                        result["error"] = "Invalid JSON response"
                    except KeyError:
                        result["error"] = "Schema definition missing for 200 OK"
                else:
                    result["error"] = f"HTTP {response.status_code}"

            except Exception as e:
                result["error"] = str(e)

            yield result
