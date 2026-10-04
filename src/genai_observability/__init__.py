"""Scaffold package for the GenAI observability privacy experiment."""

from genai_observability.runtime import apply_runtime_detectors
from genai_observability.transforms import apply_policy

__version__ = "0.1.0"

__all__ = ["apply_policy", "apply_runtime_detectors"]
