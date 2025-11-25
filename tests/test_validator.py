import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import httpx
from jsonschema import ValidationError # Import ValidationError (no longer needed in tests, but good practice)

from opnsense_openapi.client import OPNsenseClient
from opnsense_openapi.validator import SpecValidator


@pytest.fixture
def mock_spec_path(tmp_path):
    """Fixture to create a dummy spec.json file."""
    spec_content = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0"},
        "paths": {
            "/api/valid/endpoint": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "properties": {"status": {"type": "string"}}}
                                }
                            }
                        }
                    }
                }
            },
            "/api/invalid/schema": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "properties": {"count": {"type": "integer"}}}
                                }
                            }
                        }
                    }
                }
            },
            "/api/invalid/json": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        }
                    }
                }
            },
            "/api/non/json/export": {
                "get": {
                    "responses": {
                        "200": {
                            # Schema does not explicitly expect JSON
                            "description": "CSV Export"
                        }
                    }
                }
            },
            "/api/json/but/bad/content_type": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "properties": {"data": {"type": "string"}}}
                                }
                            }
                        }
                    }
                }
            },
            "/api/no/schema": {
                "get": {
                    "responses": {
                        "200": {
                            # Missing content field
                            "description": "OK"
                        }
                    }
                }
            },
            "/api/error/endpoint": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                                # No schema for 200 OK
                            }
                        }
                    }
                }
            },
            "/api/post/only": {
                "post": {
                    "responses": {"200": {"description": "OK"}}
                }
            },
            "/api/with/{param}": {
                "get": {
                    "responses": {"200": {"description": "OK"}}
                }
            },
            "/api/dangerous/delete": { # Should be skipped
                "get": {
                    "responses": {"200": {"description": "OK"}}
                }
            }
        },
        "components": {
            "schemas": {}
        }
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec_content))
    return spec_file


@pytest.fixture
def mock_client():
    """Fixture to mock OPNsenseClient."""
    client = MagicMock(spec=OPNsenseClient)
    client.base_url = "http://localhost"
    client._client = MagicMock(spec=httpx.Client)
    return client


def test_validator_initialization(mock_client, mock_spec_path):
    """Test SpecValidator initializes correctly."""
    validator = SpecValidator(mock_client, mock_spec_path)
    assert validator.spec_path == mock_spec_path
    assert "paths" in validator.spec


def test_validate_endpoints_valid(mock_client, mock_spec_path):
    """Test successful endpoint validation."""
    mock_client._client.get.return_value = httpx.Response(200, json={"status": "active"}, headers={"Content-Type": "application/json"})
    validator = SpecValidator(mock_client, mock_spec_path)
    
    results = list(validator.validate_endpoints(max_endpoints=1))
    
    assert len(results) == 1
    assert results[0]["path"] == "/api/valid/endpoint"
    assert results[0]["valid"] is True
    assert results[0]["error"] is None
    assert results[0]["status"] == 200


def test_validate_endpoints_schema_mismatch(mock_client, mock_spec_path):
    """Test schema mismatch failure."""
    mock_client._client.get.return_value = httpx.Response(200, json={"count": "ten"}, headers={"Content-Type": "application/json"}) # Expects int, gets string
    validator = SpecValidator(mock_client, mock_spec_path)
    
    results = list(validator.validate_endpoints(max_endpoints=10))
    mismatch_result = next(r for r in results if r["path"] == "/api/invalid/schema")
    
    assert mismatch_result["valid"] is False
    assert mismatch_result["error"].startswith("Schema mismatch:")
    assert "is not of type 'integer'" in mismatch_result["error"]
    assert mismatch_result["status"] == 200


def test_validate_endpoints_invalid_json(mock_client, mock_spec_path):
    """Test invalid JSON response when schema expects JSON."""
    mock_client._client.get.return_value = httpx.Response(200, content="this is not json", headers={"Content-Type": "application/json"})
    validator = SpecValidator(mock_client, mock_spec_path)
    
    results = list(validator.validate_endpoints(max_endpoints=10))
    invalid_json_result = next(r for r in results if r["path"] == "/api/invalid/json")
    
    assert invalid_json_result["valid"] is False
    assert invalid_json_result["error"] == "Invalid JSON response (server returned malformed JSON despite Content-Type)"
    assert invalid_json_result["status"] == 200


def test_validate_endpoints_non_200_status(mock_client, mock_spec_path):
    """Test non-200 HTTP status code."""
    mock_client._client.get.return_value = httpx.Response(404)
    validator = SpecValidator(mock_client, mock_spec_path)
    
    results = list(validator.validate_endpoints(max_endpoints=10))
    error_result = next(r for r in results if r["path"] == "/api/error/endpoint")
    
    assert error_result["valid"] is False
    assert error_result["error"] == "HTTP 404"
    assert error_result["status"] == 404


def test_validate_endpoints_non_json_content_type_in_response_when_schema_expects_json(mock_client, mock_spec_path):
    """Test that if schema expects JSON but response has non-JSON content-type, it fails."""
    mock_client._client.get.return_value = httpx.Response(200, content="csv,data", headers={"Content-Type": "text/csv"})
    validator = SpecValidator(mock_client, mock_spec_path)
    
    results = list(validator.validate_endpoints(max_endpoints=10))
    # This endpoint's spec expects application/json
    json_but_bad_content_type_result = next(r for r in results if r["path"] == "/api/json/but/bad/content_type")
    
    assert json_but_bad_content_type_result["valid"] is False
    assert json_but_bad_content_type_result["error"].startswith("Content-Type mismatch:")
    assert json_but_bad_content_type_result["status"] == 200


def test_validate_endpoints_missing_schema_definition(mock_client, mock_spec_path):
    """Test missing schema definition for 200 OK."""
    mock_client._client.get.return_value = httpx.Response(200, json={}) # Mock valid JSON
    validator = SpecValidator(mock_client, mock_spec_path)
    
    results = list(validator.validate_endpoints(max_endpoints=10))
    no_schema_result = next(r for r in results if r["path"] == "/api/no/schema")
    
    assert no_schema_result["valid"] is True # Now correctly asserts valid as schema does not expect JSON
    assert no_schema_result["error"].startswith("Schema does not explicitly expect JSON for 200 OK.")
    assert no_schema_result["status"] == 200


def test_validate_endpoints_skips_param_paths(mock_client, mock_spec_path):
    """Test that endpoints with path parameters are skipped."""
    validator = SpecValidator(mock_client, mock_spec_path)
    results = list(validator.validate_endpoints(max_endpoints=100)) # Ensure all are processed
    
    param_path_result = next((r for r in results if r["path"] == "/api/with/{param}"), None)
    assert param_path_result is None # Should be skipped


def test_validate_endpoints_skips_dangerous_paths(mock_client, mock_spec_path):
    """Test that dangerous paths are skipped."""
    validator = SpecValidator(mock_client, mock_spec_path)
    results = list(validator.validate_endpoints(max_endpoints=100)) # Ensure all are processed
    
    dangerous_path_result = next((r for r in results if r["path"] == "/api/dangerous/delete"), None)
    assert dangerous_path_result is None # Should be skipped


def test_validate_endpoints_max_endpoints_limit(mock_client, mock_spec_path):
    """Test max_endpoints limit."""
    # This test assumes mock_spec_path has enough endpoints to hit the limit
    mock_client._client.get.return_value = httpx.Response(200, json={"status": "active"}, headers={"Content-Type": "application/json"})
    validator = SpecValidator(mock_client, mock_spec_path)
    
    results = list(validator.validate_endpoints(max_endpoints=2))
    assert len(results) == 2 # Only 2 endpoints should be processed