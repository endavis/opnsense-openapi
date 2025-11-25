"""Example demonstrating API client diagnostics."""

import os
import json
from opnsense_openapi.client import OPNsenseClient


def run_diagnostics(
    base_url: str, api_key: str, api_secret: str, verify_ssl: bool
) -> None:
    """Run diagnostics against the OPNsense API."""
    print(f"Connecting to OPNsense at {base_url}")
    print(f"  Key: {api_key[:4]}...{api_key[-4:]}")

    client = OPNsenseClient(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        verify_ssl=verify_ssl,
    )

    successful_endpoints = []
    failed_endpoints = []

    # Get all endpoints from the API spec
    try:
        endpoints = client.list_endpoints()
    except Exception as e:
        print(f"Error listing endpoints: {e}")
        return

    print(f"\nDiscovered {len(endpoints)} API endpoints.")
    print("Testing read-only endpoints (GET requests without path parameters):")

    for path, method, summary in endpoints:
        if method != "GET" or "{" in path:
            # Skip non-GET or parameterized paths for simple diagnostics
            continue

        try:
            status = 0
            response = None
            try:
                # Use the low-level client request method directly for flexibility
                full_url = f"{client.base_url}{path}"
                response = client._client.get(full_url)
                status = response.status_code

                if status == 200:
                    try:
                        data = response.json()
                        successful_endpoints.append(
                            (method, path, data)
                        )
                    except json.JSONDecodeError:
                        successful_endpoints.append(
                            (method, path, {"text": response.text, "error": "Non-JSON response"})
                        )
                elif status == 401:
                    failed_endpoints.append((method, path, "UNAUTHORIZED"))
                else:
                    failed_endpoints.append(
                        (method, path, f"HTTP {status} - {response.text}")
                    )
            except Exception as e:
                failed_endpoints.append((method, path, f"Request failed: {e}"))

        except Exception as e:
            print(f"Error processing endpoint {path}: {e}")

    print("\n--- Diagnostic Results ---")
    print(f"Successful endpoints: {len(successful_endpoints)}")
    for method, path, data in successful_endpoints:
        print(f"  ✓ {method} {path}")

    print(f"Failed endpoints: {len(failed_endpoints)}")
    for method, path, error_msg in failed_endpoints:
        print(f"  ✗ {method} {path} - {error_msg}")

    # Example: Print detected OPNsense version
    print("\nAttempting to detect OPNsense version...")
    try:
        client._detected_version = client.detect_version()
        print(f"  ✓ Detected version: {client._detected_version}")
    except Exception as e:
        print(f"  ✗ Could not detect version: {e}")


def main() -> None:
    """Main function to run the diagnostics."""
    base_url = os.getenv("OPNSENSE_URL")
    api_key = os.getenv("OPNSENSE_API_KEY")
    api_secret = os.getenv("OPNSENSE_API_SECRET")
    verify_ssl_str = os.getenv("OPNSENSE_VERIFY_SSL", "true").lower()
    verify_ssl = verify_ssl_str == "true" or verify_ssl_str == "1"

    if not all([base_url, api_key, api_secret]):
        print("Please set OPNSENSE_URL, OPNSENSE_API_KEY, and OPNSENSE_API_SECRET environment variables.")
        return

    run_diagnostics(base_url, api_key, api_secret, verify_ssl)


if __name__ == "__main__":
    main()