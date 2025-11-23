"""Base HTTP client for OPNsense API."""

from .base import APIResponseError, OPNsenseClient
from .generated_api import GeneratedAPI

__all__ = ["APIResponseError", "OPNsenseClient", "GeneratedAPI"]
