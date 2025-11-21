"""Download OPNsense source code from GitHub."""

import logging
import shutil
import subprocess
from pathlib import Path

from ..utils import validate_version

logger = logging.getLogger(__name__)


class SourceDownloader:
    """Download and manage OPNsense source code from GitHub."""

    GITHUB_REPO = "https://github.com/opnsense/core.git"
    CONTROLLERS_PATH = "src/opnsense/mvc/app/controllers/OPNsense"

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize source downloader.

        Args:
            cache_dir: Directory to cache downloaded sources (defaults to tmp/)
        """
        self.cache_dir = cache_dir or Path("tmp/opnsense_source")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download(self, version: str, force: bool = False) -> Path:
        """Download OPNsense source for a specific version.

        Args:
            version: OPNsense version (e.g., "24.7", "24.1.1")
            force: Force re-download even if cached

        Returns:
            Path to controllers directory

        Raises:
            ValueError: If version string format is invalid
            RuntimeError: If download or git operations fail
        """
        if not validate_version(version):
            raise ValueError(
                f"Invalid version format: {version}. "
                "Expected format: XX.X or XX.X.X (e.g., 24.7, 24.7.1)"
            )
        version_dir = self.cache_dir / version
        controllers_dir = version_dir / self.CONTROLLERS_PATH

        # Check if already downloaded
        if controllers_dir.exists() and not force:
            logger.info("Using cached source for version %s", version)
            return controllers_dir

        # Clean up if forcing re-download
        if version_dir.exists() and force:
            logger.info("Removing cached source for version %s", version)
            shutil.rmtree(version_dir)

        logger.info("Downloading OPNsense %s source from GitHub...", version)

        # Clone repository with specific tag/branch
        try:
            # Try as tag first (e.g., "24.7")
            tag = f"{version}"
            self._git_clone_tag(tag, version_dir)
        except RuntimeError:
            try:
                # Try with 'v' prefix (e.g., "v24.7")
                tag = f"v{version}"
                self._git_clone_tag(tag, version_dir)
            except RuntimeError as e:
                raise RuntimeError(
                    f"Failed to download OPNsense version {version}. "
                    f"Version may not exist. Error: {e}"
                ) from e

        if not controllers_dir.exists():
            raise RuntimeError(
                f"Controllers directory not found after download: {controllers_dir}"
            )

        logger.info("Successfully downloaded to %s", controllers_dir)
        return controllers_dir

    def _git_clone_tag(self, tag: str, target_dir: Path) -> None:
        """Clone repository at specific tag.

        Args:
            tag: Git tag to clone
            target_dir: Target directory for clone

        Raises:
            RuntimeError: If git clone fails
        """
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    tag,
                    self.GITHUB_REPO,
                    str(target_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git clone failed: {e.stderr}") from e

    def get_available_versions(self) -> list[str]:
        """Get list of available OPNsense versions from GitHub tags.

        Returns:
            List of version strings

        Raises:
            RuntimeError: If git operation fails
        """
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--tags", self.GITHUB_REPO],
                check=True,
                capture_output=True,
                text=True,
            )

            # Parse tags from output
            versions = []
            for line in result.stdout.split("\n"):
                if "refs/tags/" in line:
                    tag = line.split("refs/tags/")[-1]
                    # Filter out release candidates and get clean version numbers
                    if not any(x in tag for x in ["^{}", "RC", "rc", "beta", "alpha"]):
                        versions.append(tag)

            return sorted(versions, reverse=True)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to list available versions: {e.stderr}") from e

    def clean_cache(self, version: str | None = None) -> None:
        """Clean downloaded source cache.

        Args:
            version: Specific version to clean, or None to clean all
        """
        if version:
            version_dir = self.cache_dir / version
            if version_dir.exists():
                logger.info("Cleaning cache for version %s", version)
                shutil.rmtree(version_dir)
        else:
            if self.cache_dir.exists():
                logger.info("Cleaning all cached sources")
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
