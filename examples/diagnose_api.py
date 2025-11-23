"""Diagnostic script to probe OPNsense API and identify available endpoints.

This script helps diagnose API connectivity issues and identify the correct
API structure for your OPNsense instance.
"""

import os

import httpx


def main() -> None:
    """Diagnose OPNsense API connectivity and structure."""
    base_url = os.getenv("OPNSENSE_URL", "https://opnsense.local")
    api_key = os.getenv("OPNSENSE_API_KEY", "your-api-key")
    api_secret = os.getenv("OPNSENSE_API_SECRET", "your-api-secret")
    verify_ssl = os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true"

    print("=== OPNsense API Diagnostics ===\n")
    print(f"Base URL: {base_url}")
    print(f"SSL Verification: {verify_ssl}")
    print(f"API Key: {api_key[:10]}..." if len(api_key) > 10 else f"API Key: {api_key}")
    print()

    # Create HTTP client
    client = httpx.Client(
        auth=(api_key, api_secret), verify=verify_ssl, timeout=30.0, follow_redirects=True
    )

    # Common API endpoints to test
    test_endpoints = [
        # Firmware/version endpoints
        ("core", "firmware", "status"),
        ("core", "firmware", "info"),
        ("core", "firmware", "check"),
        ("firmware", "status", "status"),
        ("firmware", "status", "info"),
        # System endpoints
        ("diagnostics", "system", "systemInformation"),
        ("system", "status", "info"),
        ("core", "system", "status"),
        # Simple test endpoints
        ("diagnostics", "interface", "getInterfaceNames"),
        ("firewall", "alias", "searchItem"),
        ("firewall", "alias_util", "findAlias"),
    ]

    print("Testing common API endpoints:\n")
    successful_endpoints = []

    for module, controller, command in test_endpoints:
        url = f"{base_url.rstrip('/')}/api/{module}/{controller}/{command}"
        try:
            response = client.get(url)
            status = response.status_code

            if status == 200:
                result = "✓ SUCCESS"
                successful_endpoints.append((module, controller, command, response.json()))
            elif status == 401:
                result = "✗ UNAUTHORIZED (check credentials)"
            elif status == 403:
                result = "✗ FORBIDDEN (insufficient permissions)"
            elif status == 404:
                result = "✗ NOT FOUND"
            elif status == 400:
                result = "✗ BAD REQUEST"
            else:
                result = f"? {status}"

            print(f"{result:30} {module}/{controller}/{command}")

        except Exception as e:
            print(f"✗ ERROR: {str(e)[:50]:30} {module}/{controller}/{command}")

    # Show successful endpoints in detail
    if successful_endpoints:
        print("\n=== Successful Endpoints (with data) ===\n")
        for module, controller, command, data in successful_endpoints:
            print(f"{module}/{controller}/{command}:")

            # Look for version information
            if "product_version" in data:
                print(f"  → Found version: {data['product_version']}")
            if "product" in data and isinstance(data["product"], dict):
                if "product_version" in data["product"]:
                    print(f"  → Found version: {data['product']['product_version']}")
                if "product_name" in data["product"]:
                    print(f"  → Product name: {data['product']['product_name']}")

            # Show first few keys of response
            if isinstance(data, dict):
                keys = list(data.keys())[:5]
                print(f"  → Response keys: {', '.join(keys)}")
                if len(data.keys()) > 5:
                    print(f"  → ... and {len(data.keys()) - 5} more")
            print()
    else:
        print("\n⚠ No successful endpoints found!")
        print("\nPossible issues:")
        print("  1. Incorrect API credentials")
        print("  2. API not enabled in OPNsense")
        print("  3. Different OPNsense version with different API structure")
        print("  4. Network/firewall blocking access")
        print("\nTroubleshooting:")
        print("  1. Verify credentials in OPNsense UI: System → Access → Users")
        print("  2. Check API is enabled: System → Settings → Administration")
        print("  3. Try accessing the URL directly in a browser")
        print(f"  4. Test URL: {base_url}/api/diagnostics/interface/getInterfaceNames")

    client.close()


if __name__ == "__main__":
    main()
