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

    # Common API endpoints to test - trying both GET and POST
    test_endpoints = [
        # Firmware/version endpoints
        ("GET", "core", "firmware", "status"),
        ("POST", "core", "firmware", "status"),
        ("GET", "core", "firmware", "info"),
        ("POST", "core", "firmware", "info"),
        ("POST", "core", "firmware", "check"),
        ("GET", "firmware", "status", "get"),
        ("POST", "firmware", "status", "get"),
        # System endpoints
        ("GET", "diagnostics", "system", "systemInformation"),
        ("POST", "diagnostics", "system", "systemInformation"),
        ("GET", "core", "system", "status"),
        ("POST", "core", "system", "status"),
        # Simple test endpoints
        ("GET", "diagnostics", "interface", "getInterfaceNames"),
        ("POST", "diagnostics", "interface", "getInterfaceNames"),
        ("GET", "firewall", "alias", "searchItem"),
        ("POST", "firewall", "alias", "searchItem"),
        ("GET", "firewall", "alias_util", "list"),
        ("POST", "firewall", "alias_util", "list"),
    ]

    print("Testing common API endpoints (GET and POST):\n")
    successful_endpoints = []

    for method, module, controller, command in test_endpoints:
        url = f"{base_url.rstrip('/')}/api/{module}/{controller}/{command}"
        try:
            if method == "GET":
                response = client.get(url)
            else:  # POST
                response = client.post(url)

            status = response.status_code

            if status == 200:
                result = "✓ SUCCESS"
                try:
                    data = response.json()
                    successful_endpoints.append((method, module, controller, command, data))
                except Exception:
                    successful_endpoints.append(
                        (method, module, controller, command, {"text": response.text})
                    )
            elif status == 401:
                result = "✗ UNAUTHORIZED"
            elif status == 403:
                result = "✗ FORBIDDEN"
            elif status == 404:
                result = "✗ NOT FOUND"
            elif status == 400:
                result = "✗ BAD REQUEST"
            else:
                result = f"? {status}"

            print(f"{method:4} {result:20} {module}/{controller}/{command}")

        except Exception as e:
            print(f"{method:4} ✗ ERROR: {str(e)[:40]:20} {module}/{controller}/{command}")

    # Show successful endpoints in detail
    if successful_endpoints:
        print("\n=== Successful Endpoints (with data) ===\n")
        for method, module, controller, command, data in successful_endpoints:
            print(f"{method} {module}/{controller}/{command}:")

            # Look for version information
            if "product_version" in data:
                print(f"  → Found version: {data['product_version']}")
            if "product" in data and isinstance(data["product"], dict):
                if "product_version" in data["product"]:
                    print(f"  → Found version: {data['product']['product_version']}")
                if "product_name" in data["product"]:
                    print(f"  → Product name: {data['product']['product_name']}")

            # Check for version in other common locations
            if "version" in data:
                print(f"  → Found version: {data['version']}")
            if (
                "system" in data
                and isinstance(data["system"], dict)
                and "version" in data["system"]
            ):
                print(f"  → Found version: {data['system']['version']}")

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
