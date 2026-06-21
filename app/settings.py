"""
App Settings
============

Shared runtime objects for the platform.
"""

from agno.models.ollama import Ollama


def default_model() -> Ollama:
    """Fresh model instance per agent — avoids shared-state footguns."""
    return Ollama(id="glm-5.1:cloud")
