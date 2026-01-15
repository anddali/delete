"""
Confluence integration plugin.
"""

import re
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional

import httpx
import structlog
from bs4 import BeautifulSoup

from .base import BaseIntegrationPlugin

logger = structlog.get_logger()


class ConfluencePlugin(BaseIntegrationPlugin):
    """Plugin for Confluence integration."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "").rstrip("/")
        self.space_keys = config.get("space_keys", [])
        credentials = self._get_credentials()
        self.email = credentials.get("email", "")
        self.api_token = credentials.get("api_token", "")
        self.options = config.get("options", {})
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=(self.email, self.api_token),
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._client
    
    async def validate_config(self) -> bool:
        """Validate Confluence configuration."""
        if not self.base_url:
            raise ValueError("base_url is required")
        if not self.space_keys:
            raise ValueError("space_keys is required")
        if not self.email or not self.api_token:
            raise ValueError("credentials.email and credentials.api_token are required")
        
        # Test API connection
        client = await self._get_client()
        response = await client.get("/rest/api/space")
        
        if response.status_code == 401:
            raise ValueError("Invalid Confluence credentials")
        elif response.status_code != 200:
            raise ValueError(f"Failed to connect to Confluence: {response.status_code}")
        
        return True
    
    async def fetch_initial(self) -> AsyncIterator[Dict[str, Any]]:
        """Fetch all pages from configured spaces."""
        client = await self._get_client()
        
        for space_key in self.space_keys:
            logger.info("Fetching Confluence space", space_key=space_key)
            
            start = 0
            limit = 100
            
            while True:
                # Fetch pages
                response = await client.get(
                    "/rest/api/content",
                    params={
                        "spaceKey": space_key,
                        "type": "page",
                        "status": "current",
                        "expand": "body.storage,version,ancestors",
                        "start": start,
                        "limit": limit,
                    },
                )
                
                if response.status_code != 200:
                    logger.error(
                        "Failed to fetch Confluence pages",
                        space_key=space_key,
                        status=response.status_code,
                    )
                    break
                
                data = response.json()
                results = data.get("results", [])
                
                for page in results:
                    try:
                        doc = await self._parse_page(page)
                        yield doc
                    except Exception as e:
                        logger.error(
                            "Failed to parse Confluence page",
                            page_id=page.get("id"),
                            error=str(e),
                        )
                
                # Check for more pages
                if len(results) < limit:
                    break
                
                start += limit
    
    async def fetch_updates(self, since: datetime) -> AsyncIterator[Dict[str, Any]]:
        """Fetch pages modified since timestamp."""
        client = await self._get_client()
        
        # Format date for CQL
        since_str = since.strftime("%Y-%m-%d %H:%M")
        
        for space_key in self.space_keys:
            logger.info(
                "Fetching Confluence updates",
                space_key=space_key,
                since=since_str,
            )
            
            start = 0
            limit = 100
            
            while True:
                # Use CQL to find modified pages
                cql = f'space = "{space_key}" AND lastModified >= "{since_str}"'
                
                response = await client.get(
                    "/rest/api/content/search",
                    params={
                        "cql": cql,
                        "expand": "body.storage,version,ancestors",
                        "start": start,
                        "limit": limit,
                    },
                )
                
                if response.status_code != 200:
                    logger.error(
                        "Failed to search Confluence",
                        status=response.status_code,
                    )
                    break
                
                data = response.json()
                results = data.get("results", [])
                
                for page in results:
                    try:
                        doc = await self._parse_page(page)
                        yield doc
                    except Exception as e:
                        logger.error(
                            "Failed to parse page",
                            page_id=page.get("id"),
                            error=str(e),
                        )
                
                if len(results) < limit:
                    break
                
                start += limit
    
    async def _parse_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Confluence page into document format."""
        page_id = page["id"]
        title = page["title"]
        
        # Get HTML content
        body = page.get("body", {}).get("storage", {})
        html_content = body.get("value", "")
        
        # Convert to plain text
        content = await self.parse_content(html_content)
        
        # Build URL
        url = f"{self.base_url}/wiki/spaces/{page.get('space', {}).get('key', '')}/pages/{page_id}"
        
        # Get metadata
        metadata = self.get_metadata(page)
        
        return {
            "external_id": page_id,
            "title": title,
            "content": content,
            "url": url,
            "metadata": metadata,
            "created_at": page.get("history", {}).get("createdDate"),
            "updated_at": page.get("version", {}).get("when"),
        }
    
    async def parse_content(self, raw_content: Any) -> str:
        """Convert HTML content to plain text."""
        if not raw_content:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(raw_content, "lxml")
        
        # Remove scripts and styles
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        
        # Handle code blocks specially
        for code in soup.find_all("code"):
            code.string = f"\n```\n{code.get_text()}\n```\n"
        
        # Get text
        text = soup.get_text(separator="\n")
        
        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)
        
        # Remove excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        return text.strip()
    
    def get_metadata(self, raw_doc: Any) -> Dict[str, Any]:
        """Extract metadata from Confluence page."""
        return {
            "space_key": raw_doc.get("space", {}).get("key"),
            "space_name": raw_doc.get("space", {}).get("name"),
            "version": raw_doc.get("version", {}).get("number"),
            "author": raw_doc.get("version", {}).get("by", {}).get("displayName"),
            "ancestors": [
                {"id": a.get("id"), "title": a.get("title")}
                for a in raw_doc.get("ancestors", [])
            ],
            "labels": [
                label.get("name")
                for label in raw_doc.get("metadata", {}).get("labels", {}).get("results", [])
            ],
        }
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
