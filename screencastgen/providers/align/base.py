"""Shared metadata for alignment providers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AlignmentProviderSpec:
    """Metadata describing an alignment provider."""

    name: str
    module_path: str
    function_name: str
