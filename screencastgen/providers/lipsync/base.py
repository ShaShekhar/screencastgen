"""Shared metadata for lip-sync providers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LipsyncProviderSpec:
    """Metadata describing a lip-sync provider."""

    name: str
    module_path: str
    function_name: str
