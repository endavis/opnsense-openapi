"""Command-line interface for the OPNsense API wrapper toolkit."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .downloader import SourceDownloader

# ENFORCE: Ensure your generator file is named 'generator.py'
# or update this import to 'from .openapi_generator import OpenApiGenerator'
from .generator import OpenApiGenerator
from .parser import ControllerParser
from .specs import find_best_matching_spec, list_available_specs

app = typer.Typer(help="Generate and inspect OPNsense API wrappers.")


def _version_callback(show_version: bool) -> None:
    if show_version:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    _: Annotated[
        bool,
        typer.Option(
            "--version",
            is_eager=True,
            help="Print the current opnsense-api version and exit.",
            callback=_version_callback,
        ),
    ] = False,
) -> None:
    """Global CLI options."""


@app.command()
def download(
    version: Annotated[str, typer.Argument(help="OPNsense release tag, e.g. 24.7")],
    dest: Annotated[
        Path | None,
        typer.Option(
            "--dest",
            "-d",
            help="Directory for cached controller sources (defaults to tmp/opnsense_source).",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force/--no-force", help="Re-download files even when cached."),
    ] = False,
) -> None:
    """Download controller files for the specified firmware release."""

    downloader = SourceDownloader(cache_dir=dest)
    try:
        controllers_path = downloader.download(version, force=force)
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(
        f"Stored controller files for {version} under {controllers_path}",
        fg=typer.colors.GREEN,
    )


@app.command()
def generate(
    version: Annotated[str, typer.Argument(help="OPNsense release tag, e.g. 24.7")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for generated OpenAPI spec (defaults to specs/).",
        ),
    ] = None,
    cache: Annotated[
        Path | None,
        typer.Option(
            "--cache",
            "-c",
            help="Directory for cached source files (defaults to tmp/opnsense_source).",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force/--no-force", help="Re-download source even when cached."),
    ] = False,
) -> None:
    """Generate OpenAPI spec for the specified OPNsense version."""
    # Default to specs/ directory in package
    if output is None:
        output_dir = Path(__file__).parent / "specs"
    else:
        output_dir = output
    output_dir.mkdir(parents=True, exist_ok=True)
    downloader = SourceDownloader(cache_dir=cache)

    # Download source
    try:
        typer.echo(f"Downloading OPNsense {version} source...")
        controllers_path = downloader.download(version, force=force)
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    # --- FIX START ---
    # Derive models path. The generator appends the Vendor (OPNsense),
    # so we must point to the root 'models' directory.
    # Structure: .../src/opnsense/mvc/app/models
    models_path = controllers_path.parent.parent / "models"
    # --- FIX END ---

    # Parse controllers
    typer.echo("Parsing controllers...")
    parser = ControllerParser()
    controllers = parser.parse_directory(controllers_path)
    typer.echo(f"  Found {len(controllers)} controllers")

    # Generate OpenAPI spec
    typer.echo("Generating OpenAPI specification...")
    generator = OpenApiGenerator(output_dir)

    # Validate models_path exists before passing
    valid_models_path = models_path if models_path.exists() else None
    if valid_models_path:
        typer.echo(f"  Using models directory: {valid_models_path}")
    else:
        typer.secho("  Warning: Models directory not found. Schema generation will be skipped.", fg=typer.colors.YELLOW)

    output_file = generator.generate(
        controllers,
        version,
        models_dir=valid_models_path,
        controllers_dir=controllers_path,
    )

    typer.secho(f"Generated {output_file}", fg=typer.colors.GREEN)


@app.command(name="serve-docs")
def serve_docs(
    version: Annotated[
        str | None,
        typer.Option(
            "--version",
            "-v",
            help="OPNsense version (e.g., '25.7.6'). Auto-detects if not specified.",
        ),
    ] = None,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to run server on"),
    ] = 8080,
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "127.0.0.1",
    list_versions: Annotated[
        bool,
        typer.Option("--list", "-l", help="List available spec versions and exit"),
    ] = False,
    no_auto_detect: Annotated[
        bool,
        typer.Option("--no-auto-detect", help="Disable auto-detection (requires --version)"),
    ] = False,
) -> None:
    """Launch Swagger UI server for browsing OPNsense API documentation."""
    # List versions and exit
    if list_versions:
        typer.echo("Available OPNsense API spec versions:")
        for spec_version in list_available_specs():
            typer.echo(f"  - {spec_version}")
        return

    # Validate arguments
    if no_auto_detect and not version:
        typer.secho(
            "Error: --no-auto-detect requires --version to be specified",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    # Import Flask dependencies (only when needed)
    try:
        from flask import Flask, jsonify, make_response, redirect, request
        from flask_swagger_ui import get_swaggerui_blueprint
    except ImportError:
        typer.secho(
            "Error: Flask dependencies not installed.",
            fg=typer.colors.RED,
            err=True,
        )
        typer.echo("Install with: uv pip install opnsense-openapi[ui]")
        raise typer.Exit(code=1)

    # Determine which version to use
    version_to_use = version

    if not no_auto_detect and version is None:
        typer.echo("Attempting to auto-detect OPNsense version...")
        try:
            from .client import OPNsenseClient

            client = OPNsenseClient(
                base_url=os.getenv("OPNSENSE_URL", "https://opnsense.local"),
                api_key=os.getenv("OPNSENSE_API_KEY", ""),
                api_secret=os.getenv("OPNSENSE_API_SECRET", ""),
                verify_ssl=os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true",
                auto_detect_version=True,
            )
            if client._detected_version:
                version_to_use = client._detected_version
                typer.secho(f"✓ Detected version: {version_to_use}", fg=typer.colors.GREEN)
            else:
                typer.secho("⚠ Could not auto-detect version", fg=typer.colors.YELLOW)
        except Exception as e:
            typer.secho(f"⚠ Auto-detection failed: {e}", fg=typer.colors.YELLOW)

    # Find the spec file to use
    if version_to_use:
        try:
            spec_path = find_best_matching_spec(version_to_use)
            typer.echo(f"Using spec file: {spec_path}")
        except FileNotFoundError:
            typer.secho(
                f"Error: No spec file found for version {version_to_use}",
                fg=typer.colors.RED,
                err=True,
            )
            typer.echo(f"Available versions: {', '.join(list_available_specs())}")
            raise typer.Exit(code=1)
    else:
        # No version specified and auto-detect failed, use latest available
        available = list_available_specs()
        if not available:
            typer.secho(
                "Error: No spec files found in specs directory",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        version_to_use = available[-1]  # Use latest version
        spec_path = find_best_matching_spec(version_to_use)
        typer.echo(f"Using latest available spec: {version_to_use}")

    # Create Flask app
    flask_app = Flask(__name__)

    # Initialize OPNsense client for proxy if credentials are available
    opnsense_client = None
    opnsense_url = os.getenv("OPNSENSE_URL")
    api_key = os.getenv("OPNSENSE_API_KEY")
    api_secret = os.getenv("OPNSENSE_API_SECRET")

    if opnsense_url and api_key and api_secret:
        try:
            from .client import OPNsenseClient
            opnsense_client = OPNsenseClient(
                base_url=opnsense_url,
                api_key=api_key,
                api_secret=api_secret,
                verify_ssl=os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true",
            )
            typer.echo(f"✓ Proxy enabled for {opnsense_url}")
        except Exception as e:
            typer.secho(f"⚠ Could not initialize proxy client: {e}", fg=typer.colors.YELLOW)

    # Configure Swagger UI
    swagger_url = "/api/docs"
    api_url = "/api/spec"

    swaggerui_blueprint = get_swaggerui_blueprint(
        swagger_url,
        api_url,
        config={
            "app_name": f"OPNsense API Documentation - v{version_to_use}",
            "defaultModelsExpandDepth": -1,
            "docExpansion": "list",
            "displayRequestDuration": True,
            "filter": True,
        },
    )

    flask_app.register_blueprint(swaggerui_blueprint, url_prefix=swagger_url)

    # Serve the OpenAPI spec file
    @flask_app.route("/api/spec")
    def api_spec():
        """Serve the OpenAPI specification file."""
        import json

        with open(spec_path) as f:
            spec = json.load(f)

        # If proxy is enabled, update server URL to use the proxy
        if opnsense_client:
            spec["servers"] = [
                {
                    "url": f"http://{host}:{port}/proxy",
                    "description": "Local proxy to OPNsense instance"
                }
            ]

        return jsonify(spec)

    # Proxy endpoint to forward requests to OPNsense instance
    @flask_app.route("/proxy/<path:api_path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def proxy(api_path):
        """Proxy requests to the actual OPNsense instance."""
        if not opnsense_client:
            return jsonify({
                "error": "Proxy not configured",
                "message": "Set OPNSENSE_URL, OPNSENSE_API_KEY, and OPNSENSE_API_SECRET environment variables"
            }), 503

        try:
            # Build full URL to OPNsense instance
            url = f"{opnsense_client.base_url}/api/{api_path}"

            # Get request data
            json_data = request.get_json(silent=True) if request.is_json else None
            params = dict(request.args)

            # Forward the request using the underlying httpx client
            httpx_response = opnsense_client._client.request(
                method=request.method,
                url=url,
                params=params,
                json=json_data,
            )
            httpx_response.raise_for_status()

            # Parse response as JSON
            response_data = httpx_response.json()

            # Create response with CORS headers
            response = make_response(jsonify(response_data))
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

            return response

        except Exception as e:
            error_response = jsonify({
                "error": "Proxy request failed",
                "message": str(e)
            })
            error_response.headers["Access-Control-Allow-Origin"] = "*"
            return error_response, 500

    # Handle OPTIONS requests for CORS preflight
    @flask_app.route("/proxy/<path:api_path>", methods=["OPTIONS"])
    def proxy_options(api_path):
        """Handle CORS preflight requests."""
        response = make_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    # Root redirect
    @flask_app.route("/")
    def index():
        """Redirect to Swagger UI."""
        return redirect(swagger_url)

    # Start server
    typer.echo("=" * 70)
    typer.secho("🚀 OPNsense API Documentation Server", fg=typer.colors.CYAN, bold=True)
    typer.echo("=" * 70)
    typer.echo(f"\n📖 Open your browser to: http://{host}:{port}/api/docs")
    typer.echo(f"📄 Serving spec for version: {version_to_use}")
