"""Command-line interface for the OPNsense API wrapper toolkit."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .downloader import SourceDownloader
from .generator import OpenApiGenerator
from .parser import ControllerParser

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

    # Derive models path from controllers path
    # controllers: .../src/opnsense/mvc/app/controllers/OPNsense
    # models:      .../src/opnsense/mvc/app/models/OPNsense
    models_path = controllers_path.parent.parent / "models" / "OPNsense"

    # Parse controllers
    typer.echo("Parsing controllers...")
    parser = ControllerParser()
    controllers = parser.parse_directory(controllers_path)
    typer.echo(f"  Found {len(controllers)} controllers")

    # Generate OpenAPI spec
    typer.echo("Generating OpenAPI specification...")
    generator = OpenApiGenerator(output_dir)
    output_file = generator.generate(
        controllers,
        version,
        models_dir=models_path if models_path.exists() else None,
    )

    typer.secho(f"Generated {output_file}", fg=typer.colors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    app()
