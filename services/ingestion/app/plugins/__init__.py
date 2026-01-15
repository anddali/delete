"""
Integration plugins for different data sources.
"""

from .base import BaseIntegrationPlugin, Document
from .confluence import ConfluencePlugin
from .slack import SlackPlugin
from .file_upload import FileUploadPlugin

# Plugin registry
PLUGIN_REGISTRY = {
    "confluence": ConfluencePlugin,
    "slack": SlackPlugin,
    "file_upload": FileUploadPlugin,
}


def get_plugin(source_type: str, config: dict) -> BaseIntegrationPlugin:
    """Get plugin instance for source type."""
    plugin_class = PLUGIN_REGISTRY.get(source_type)
    if not plugin_class:
        raise ValueError(f"Unknown source type: {source_type}")
    return plugin_class(config)


__all__ = [
    "BaseIntegrationPlugin",
    "Document",
    "ConfluencePlugin",
    "SlackPlugin",
    "FileUploadPlugin",
    "get_plugin",
    "PLUGIN_REGISTRY",
]
