"""Base HTTP client for OPNsense API."""

from .base import APIResponseError, OPNsenseClient, UnknownEndpointError
from .generated_api import GeneratedAPI

__all__ = ["APIResponseError", "GeneratedAPI", "OPNsenseClient", "UnknownEndpointError"]
