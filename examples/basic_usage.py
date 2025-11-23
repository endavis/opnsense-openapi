"""Example usage of OPNsense API client with OpenAPI integration.

This example demonstrates how to use the OPNsense API client with automatic
version detection and OpenAPI endpoint discovery.

Prerequisites:
1. Set environment variables or update the credentials below
2. Ensure network access to your OPNsense instance
"""

import os

from opnsense_api.client import OPNsenseClient


def main() -> None:
    """Example demonstrating basic API usage with OpenAPI features."""
    # Initialize client with automatic version detection
    print("=== Initializing Client ===")

    # Try to use specified version from environment, or auto-detect
    spec_version = os.getenv("OPNSENSE_VERSION")

    client = OPNsenseClient(
        base_url=os.getenv("OPNSENSE_URL", "https://opnsense.local"),
        api_key=os.getenv("OPNSENSE_API_KEY", "your-api-key"),
        api_secret=os.getenv("OPNSENSE_API_SECRET", "your-api-secret"),
        verify_ssl=os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true",
        spec_version=spec_version,  # Use specified version if provided
        auto_detect_version=spec_version is None,  # Only auto-detect if not specified
    )

    if spec_version:
        print(f"Using specified version: {spec_version}")
    elif client._detected_version:
        print(f"Auto-detected version: {client._detected_version}")
    else:
        print("Warning: Could not detect version. OpenAPI features will be unavailable.")
        print("Set OPNSENSE_VERSION environment variable to use OpenAPI features.")

    try:
        # Example 1: Traditional client API usage
        print("\n=== System Information (Traditional API) ===")
        try:
            info = client.get("core", "firmware", "info")
            if "product_version" in info:
                print(f"OPNsense Version: {info['product_version']}")
            if "product" in info and "product_name" in info["product"]:
                print(f"Product Name: {info['product']['product_name']}")
        except Exception as e:
            print(f"Could not get firmware info: {e}")

        # Example 2: List firewall aliases using the client API
        print("\n=== Firewall Aliases ===")
        try:
            aliases = client.get("firewall", "alias_util", "findAlias")
            alias_count = len(aliases.get("rows", []))
            print(f"Found {alias_count} aliases")
            for alias in aliases.get("rows", [])[:5]:
                name = alias.get("name", "N/A")
                desc = alias.get("description", "No description")
                print(f"  - {name}: {desc}")
        except Exception as e:
            print(f"Could not fetch aliases (endpoint may not exist on this version): {e}")

        # Example 3: Using OpenAPI endpoint discovery
        print("\n=== OpenAPI Endpoint Discovery ===")
        try:
            endpoints = client.list_endpoints()
            print(f"Total endpoints available: {len(endpoints)}")

            # Find and display firewall-related endpoints
            firewall_endpoints = [
                (path, method) for path, method, _ in endpoints if "firewall" in path.lower()
            ]
            print(f"Firewall endpoints: {len(firewall_endpoints)}")

            # Example 4: Get detailed information about an endpoint
            print("\n=== Endpoint Details ===")
            if firewall_endpoints:
                example_path, example_method = firewall_endpoints[0]
                info = client.get_endpoint_info(example_path, example_method)
                print(f"Endpoint: {example_method} {example_path}")
                print(f"Summary: {info.get('summary', 'No summary available')}")

                if info["path_params"]:
                    print(f"Path parameters: {len(info['path_params'])}")
                if info["query_params"]:
                    print(f"Query parameters: {len(info['query_params'])}")
        except RuntimeError as e:
            print(f"OpenAPI features not available: {e}")
            print("Tip: Set OPNSENSE_VERSION environment variable (e.g., '24.7.1')")

        # Example 5: Using context manager
        print("\n=== Using Context Manager ===")
        with OPNsenseClient(
            base_url=os.getenv("OPNSENSE_URL", "https://opnsense.local"),
            api_key=os.getenv("OPNSENSE_API_KEY", "your-api-key"),
            api_secret=os.getenv("OPNSENSE_API_SECRET", "your-api-secret"),
            verify_ssl=os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true",
            spec_version=spec_version,
            auto_detect_version=spec_version is None,
        ) as ctx_client:
            # Can use both traditional and OpenAPI methods
            try:
                firmware_info = ctx_client.get("core", "firmware", "info")
                print(f"Firmware info retrieved: {bool(firmware_info)}")
            except Exception:
                print("Could not retrieve firmware info via context manager")

            try:
                endpoint_count = len(ctx_client.list_endpoints())
                print(f"Available endpoints: {endpoint_count}")
            except RuntimeError:
                print("OpenAPI features not available in this session")

    except Exception as e:
        print(f"\nError: {e}")
        print("Note: Make sure OPNsense is accessible and credentials are correct")
        return

    print("\n✓ Example completed successfully")


if __name__ == "__main__":
    main()
