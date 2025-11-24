"""Swagger UI server for browsing OPNsense API documentation.

This script launches a local web server that serves Swagger UI for exploring
the OPNsense OpenAPI specification for a specific version.

Usage:
    # Auto-detect version from your OPNsense instance
    uv run python examples/swagger_ui_server.py

    # Or specify a version explicitly
    uv run python examples/swagger_ui_server.py --version 25.7.6

    # List available versions
    uv run python examples/swagger_ui_server.py --list

Then open http://localhost:8080 in your browser.
"""

import argparse
import os
import sys

from flask import Flask, jsonify
from flask_swagger_ui import get_swaggerui_blueprint

from opnsense_api.client import OPNsenseClient
from opnsense_api.specs import find_best_matching_spec, list_available_specs
import httpx


def create_app(spec_version: str | None = None, auto_detect: bool = True) -> Flask:
    """Create Flask app with Swagger UI.

    Args:
        spec_version: Specific version to use, or None to auto-detect
        auto_detect: Whether to auto-detect version from OPNsense server

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)

    # Determine which version to use
    version_to_use = spec_version

    if auto_detect and spec_version is None:
        print("Attempting to auto-detect OPNsense version...")
        try:
            client = OPNsenseClient(
                base_url=os.getenv("OPNSENSE_URL", "https://opnsense.local"),
                api_key=os.getenv("OPNSENSE_API_KEY", ""),
                api_secret=os.getenv("OPNSENSE_API_SECRET", ""),
                verify_ssl=os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true",
                auto_detect_version=True,
            )
            if client._detected_version:
                version_to_use = client._detected_version
                print(f"✓ Detected version: {version_to_use}")
            else:
                print("⚠ Could not auto-detect version")
        except Exception as e:
            print(f"⚠ Auto-detection failed: {e}")

    # Find the spec file to use
    if version_to_use:
        try:
            spec_path = find_best_matching_spec(version_to_use)
            print(f"Using spec file: {spec_path}")
        except FileNotFoundError:
            print(f"Error: No spec file found for version {version_to_use}")
            print(f"Available versions: {', '.join(list_available_specs())}")
            sys.exit(1)
    else:
        # No version specified and auto-detect failed, use latest available
        available = list_available_specs()
        if not available:
            print("Error: No spec files found in specs directory")
            sys.exit(1)
        version_to_use = available[-1]  # Use latest version
        spec_path = find_best_matching_spec(version_to_use)
        print(f"Using latest available spec: {version_to_use}")

    # Configure Swagger UI
    swagger_url = "/api/docs"  # URL for exposing Swagger UI
    api_url = "/api/spec"  # URL for serving the OpenAPI spec

    swaggerui_blueprint = get_swaggerui_blueprint(
        swagger_url,
        api_url,
        config={
            "app_name": f"OPNsense API Documentation - v{version_to_use}",
            "defaultModelsExpandDepth": -1,  # Hide models by default
            "docExpansion": "list",  # Expand operations by default
            "displayRequestDuration": True,
            "filter": True,  # Enable search/filter
        },
    )

    app.register_blueprint(swaggerui_blueprint, url_prefix=swagger_url)

    # Serve the OpenAPI spec file
    @app.route("/api/spec")
    def api_spec():
        """Serve the OpenAPI specification file."""
        with open(spec_path) as f:
            import json

            spec = json.load(f)

        # Update servers field to use local proxy endpoint
        # This avoids CORS issues by proxying requests through the Flask server
        opnsense_url = os.getenv("OPNSENSE_URL")
        if opnsense_url:
            spec["servers"] = [
                {
                    "url": "/proxy",
                    "description": f"OPNsense Server Proxy ({opnsense_url})"
                }
            ]
        else:
            spec["servers"] = [
                {
                    "url": "https://localhost/api",
                    "description": "OPNsense Server (set OPNSENSE_URL to enable proxy)"
                }
            ]

        return jsonify(spec)

    # Proxy endpoint to forward API requests to OPNsense server
    @app.route("/proxy/<path:endpoint>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def proxy(endpoint: str):
        """Proxy API requests to OPNsense server to avoid CORS issues."""
        from flask import request, Response
        import base64

        opnsense_url = os.getenv("OPNSENSE_URL")
        api_key = os.getenv("OPNSENSE_API_KEY")
        api_secret = os.getenv("OPNSENSE_API_SECRET")
        verify_ssl = os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true"

        if not all([opnsense_url, api_key, api_secret]):
            return jsonify({
                "error": "OPNsense credentials not configured",
                "message": "Set OPNSENSE_URL, OPNSENSE_API_KEY, and OPNSENSE_API_SECRET environment variables"
            }), 500

        # Build target URL
        base_url = opnsense_url.rstrip("/")
        if base_url.endswith("/api"):
            base_url = base_url[:-4]
        target_url = f"{base_url}/api/{endpoint}"

        # Add query parameters if present
        if request.query_string:
            target_url += f"?{request.query_string.decode()}"

        # Prepare authentication
        auth_string = f"{api_key}:{api_secret}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

        # Prepare headers
        headers = {
            "Authorization": f"Basic {auth_b64}",
        }

        # Only add Content-Type for requests with JSON body
        if request.is_json or request.method in ["POST", "PUT", "PATCH"]:
            headers["Content-Type"] = "application/json"

        # Forward request
        try:
            with httpx.Client(verify=verify_ssl, timeout=30.0) as client:
                if request.method == "GET":
                    response = client.get(target_url, headers=headers)
                elif request.method == "POST":
                    response = client.post(
                        target_url,
                        headers=headers,
                        json=request.get_json() if request.is_json else None,
                        data=request.data if not request.is_json else None,
                    )
                elif request.method == "PUT":
                    response = client.put(
                        target_url,
                        headers=headers,
                        json=request.get_json() if request.is_json else None,
                        data=request.data if not request.is_json else None,
                    )
                elif request.method == "DELETE":
                    response = client.delete(target_url, headers=headers)
                elif request.method == "PATCH":
                    response = client.patch(
                        target_url,
                        headers=headers,
                        json=request.get_json() if request.is_json else None,
                        data=request.data if not request.is_json else None,
                    )
                else:
                    return jsonify({"error": "Method not supported"}), 405

                # Return response with filtered headers
                # Filter out headers that shouldn't be forwarded
                excluded_headers = {
                    "content-encoding",
                    "content-length",
                    "transfer-encoding",
                    "connection",
                }
                response_headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in excluded_headers
                }

                return Response(
                    response.content,
                    status=response.status_code,
                    headers=response_headers,
                )
        except Exception as e:
            return jsonify({"error": "Proxy request failed", "message": str(e)}), 500

    # Root redirect
    @app.route("/")
    def index():
        """Redirect to Swagger UI."""
        from flask import redirect

        return redirect(swagger_url)

    return app


def main() -> None:
    """Run the Swagger UI server."""
    parser = argparse.ArgumentParser(description="Launch Swagger UI for OPNsense API documentation")
    parser.add_argument(
        "--version",
        "-v",
        help="OPNsense version (e.g., '25.7.6'). If not specified, will auto-detect.",
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="List available spec versions and exit"
    )
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to run server on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument(
        "--no-auto-detect",
        action="store_true",
        help="Disable auto-detection (requires --version)",
    )

    args = parser.parse_args()

    # List versions and exit
    if args.list:
        print("Available OPNsense API spec versions:")
        for version in list_available_specs():
            print(f"  - {version}")
        return

    # Validate arguments
    if args.no_auto_detect and not args.version:
        parser.error("--no-auto-detect requires --version")

    # Create and run app
    app = create_app(spec_version=args.version, auto_detect=not args.no_auto_detect)

    print("\n" + "=" * 70)
    print("🚀 OPNsense API Documentation Server")
    print("=" * 70)
    print(f"\n📖 Open your browser to: http://{args.host}:{args.port}/api/docs")
    print("\n💡 Tip: Use Ctrl+C to stop the server\n")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
