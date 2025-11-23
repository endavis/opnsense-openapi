"""Example usage of OpenAPI integration with OPNsense client.

This example demonstrates how to use the integrated OpenAPI features
to discover and introspect API endpoints.

Prerequisites:
1. Set environment variables or update the credentials below
2. Ensure network access to your OPNsense instance
"""

import os

from opnsense_api.client import OPNsenseClient


def main() -> None:
    """Example demonstrating OpenAPI integration."""
    # Initialize client with automatic version detection
    print("=== Initializing Client ===")
    client = OPNsenseClient(
        base_url=os.getenv("OPNSENSE_URL", "https://opnsense.local"),
        api_key=os.getenv("OPNSENSE_API_KEY", "your-api-key"),
        api_secret=os.getenv("OPNSENSE_API_SECRET", "your-api-secret"),
        verify_ssl=os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true",
        auto_detect_version=True,  # Automatically detect version from server
    )

    # Alternative: Specify version explicitly
    # client = OPNsenseClient(
    #     base_url="https://opnsense.local",
    #     api_key="your-api-key",
    #     api_secret="your-api-secret",
    #     spec_version="24.7.1",  # Use specific version
    #     auto_detect_version=False,
    # )

    try:
        # Example 1: List all available endpoints
        print("\n=== Available Endpoints (first 10) ===")
        endpoints = client.list_endpoints()
        print(f"Total endpoints: {len(endpoints)}")
        for path, method, summary in endpoints[:10]:
            summary_text = summary if summary else "No description"
            print(f"  {method:7} {path:50} - {summary_text}")

        # Example 2: Search for specific endpoints
        print("\n=== Firewall-related Endpoints ===")
        firewall_endpoints = [
            (path, method, summary)
            for path, method, summary in endpoints
            if "firewall" in path.lower()
        ]
        print(f"Found {len(firewall_endpoints)} firewall endpoints")
        for path, method, summary in firewall_endpoints[:5]:
            print(f"  {method:7} {path}")

        # Example 3: Get detailed endpoint information
        print("\n=== Endpoint Details ===")
        # Pick a common endpoint to inspect
        if firewall_endpoints:
            example_path, example_method, _ = firewall_endpoints[0]
            info = client.get_endpoint_info(example_path, example_method)

            print(f"Endpoint: {example_method} {info['path']}")
            print(f"Summary: {info.get('summary', 'N/A')}")

            if info["path_params"]:
                print("\nPath Parameters:")
                for param in info["path_params"]:
                    req = "required" if param["required"] else "optional"
                    print(f"  - {param['name']} ({param['type']}, {req})")

            if info["query_params"]:
                print("\nQuery Parameters:")
                for param in info["query_params"]:
                    req = "required" if param["required"] else "optional"
                    print(f"  - {param['name']} ({param['type']}, {req})")

            if info.get("body_sample"):
                print("\nExample Request Body:")
                print(f"  {info['body_sample']}")

        # Example 4: Access the underlying OpenAPI wrapper
        print("\n=== Direct OpenAPI Access ===")
        openapi = client.openapi
        print(f"OpenAPI wrapper initialized: {openapi is not None}")
        print(f"Base URL: {openapi.base_url}")
        print(f"Spec file loaded: Yes")

    except Exception as e:
        print(f"Error: {e}")
        return

    print("\n✓ Example completed successfully")


if __name__ == "__main__":
    main()
