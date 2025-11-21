"""Example usage of generated OPNsense API wrapper.

This example demonstrates how to use the generated API client to interact
with an OPNsense firewall.

Prerequisites:
1. Generate the wrapper: just generate 24.7
2. Set environment variables or update the credentials below
3. Ensure network access to your OPNsense instance
"""

import os
from pathlib import Path
import sys

# Add generated code to path
sys.path.insert(0, str(Path(__file__).parent.parent / "generated"))

from opnsense_api.client import OPNsenseClient


def main() -> None:
    """Example demonstrating basic API usage."""
    # Initialize client with your OPNsense credentials
    client = OPNsenseClient(
        base_url=os.getenv("OPNSENSE_URL", "https://opnsense.local"),
        api_key=os.getenv("OPNSENSE_API_KEY", "your-api-key"),
        api_secret=os.getenv("OPNSENSE_API_SECRET", "your-api-secret"),
        verify_ssl=os.getenv("OPNSENSE_VERIFY_SSL", "true").lower() == "true",
    )

    try:
        # Example 1: Get system information
        print("=== System Information ===")
        # Note: These are example calls - actual methods depend on generated code
        # system = System(client)
        # info = system.info.version()
        # print(f"Version: {info}")

        # Example 2: List firewall aliases
        print("\n=== Firewall Aliases ===")
        # firewall = Firewall(client)
        # aliases = firewall.alias_util.find_alias()
        # for alias in aliases.get('rows', []):
        #     print(f"  - {alias.get('name')}: {alias.get('description')}")

        # Example 3: Using context manager
        print("\n=== Using Context Manager ===")
        with OPNsenseClient(
            base_url=os.getenv("OPNSENSE_URL", "https://opnsense.local"),
            api_key=os.getenv("OPNSENSE_API_KEY"),
            api_secret=os.getenv("OPNSENSE_API_SECRET"),
        ) as ctx_client:
            # Make API calls
            # result = ctx_client.get("system", "info", "version")
            # print(result)
            pass

    except Exception as e:
        print(f"Error: {e}")
        return

    print("\n✓ Example completed successfully")


if __name__ == "__main__":
    main()
