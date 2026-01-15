"""
Base plugin interface for integration plugins.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional


@dataclass
class Document:
    """Represents a document from a source."""
    
    external_id: str
    title: str
    content: str
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BaseIntegrationPlugin(ABC):
    """
    Base class for all integration plugins.
    
    Each plugin must implement methods for:
    - Validating configuration
    - Fetching initial data (full sync)
    - Fetching updates (incremental sync)
    - Parsing content to plain text
    - Extracting metadata
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize plugin with configuration.
        
        Args:
            config: Plugin-specific configuration from source.config
        """
        self.config = config
        self._rate_limiter = None
    
    @abstractmethod
    async def validate_config(self) -> bool:
        """
        Validate configuration and credentials.
        
        Returns:
            True if configuration is valid
        
        Raises:
            ValueError: If configuration is invalid
        """
        pass
    
    @abstractmethod
    async def fetch_initial(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Fetch all documents for initial sync.
        
        Yields:
            Document data dictionaries with keys:
                - external_id: Unique ID in source system
                - title: Document title
                - content: Plain text content
                - url: Optional URL
                - metadata: Optional metadata dict
        """
        pass
    
    @abstractmethod
    async def fetch_updates(self, since: datetime) -> AsyncIterator[Dict[str, Any]]:
        """
        Fetch documents modified since timestamp.
        
        Args:
            since: Fetch documents modified after this time
        
        Yields:
            Document data dictionaries
        """
        pass
    
    @abstractmethod
    async def parse_content(self, raw_content: Any) -> str:
        """
        Parse raw content into plain text.
        
        Args:
            raw_content: Raw content from source
        
        Returns:
            Plain text content
        """
        pass
    
    @abstractmethod
    def get_metadata(self, raw_doc: Any) -> Dict[str, Any]:
        """
        Extract metadata from document.
        
        Args:
            raw_doc: Raw document from source
        
        Returns:
            Metadata dictionary
        """
        pass
    
    async def check_health(self) -> bool:
        """
        Check if integration is accessible.
        
        Returns:
            True if source is reachable and credentials are valid
        """
        try:
            return await self.validate_config()
        except Exception:
            return False
    
    def _get_credentials(self) -> Dict[str, str]:
        """Get decrypted credentials from config."""
        credentials = self.config.get("credentials", {})
        # In production, decrypt credentials here
        return credentials
