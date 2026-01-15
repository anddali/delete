"""
Slack integration plugin.
"""

import re
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from .base import BaseIntegrationPlugin

logger = structlog.get_logger()


class SlackPlugin(BaseIntegrationPlugin):
    """Plugin for Slack integration."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.workspace_id = config.get("workspace_id", "")
        self.channel_ids = config.get("channel_ids", [])
        credentials = self._get_credentials()
        self.bot_token = credentials.get("bot_token", "")
        self.options = config.get("options", {})
        
        # Slack client
        self._client: Optional[AsyncWebClient] = None
        self._user_cache: Dict[str, str] = {}
    
    def _get_client(self) -> AsyncWebClient:
        """Get or create Slack client."""
        if self._client is None:
            self._client = AsyncWebClient(token=self.bot_token)
        return self._client
    
    async def validate_config(self) -> bool:
        """Validate Slack configuration."""
        if not self.channel_ids:
            raise ValueError("channel_ids is required")
        if not self.bot_token:
            raise ValueError("credentials.bot_token is required")
        
        # Test API connection
        try:
            client = self._get_client()
            response = await client.auth_test()
            
            if not response["ok"]:
                raise ValueError("Invalid Slack bot token")
            
            logger.info(
                "Slack auth successful",
                team=response.get("team"),
                user=response.get("user"),
            )
            
            return True
        
        except SlackApiError as e:
            raise ValueError(f"Slack API error: {e.response['error']}")
    
    async def fetch_initial(self) -> AsyncIterator[Dict[str, Any]]:
        """Fetch all messages from configured channels."""
        client = self._get_client()
        
        for channel_id in self.channel_ids:
            logger.info("Fetching Slack channel", channel_id=channel_id)
            
            # Get channel info
            try:
                channel_info = await client.conversations_info(channel=channel_id)
                channel_name = channel_info["channel"]["name"]
            except SlackApiError:
                channel_name = channel_id
            
            cursor = None
            
            while True:
                try:
                    # Fetch messages
                    response = await client.conversations_history(
                        channel=channel_id,
                        cursor=cursor,
                        limit=200,
                    )
                    
                    messages = response.get("messages", [])
                    
                    for message in messages:
                        # Skip bot messages if configured
                        if message.get("subtype") == "bot_message":
                            continue
                        
                        # Check minimum length
                        text = message.get("text", "")
                        min_length = self.options.get("min_message_length", 10)
                        if len(text) < min_length:
                            continue
                        
                        doc = await self._parse_message(
                            message, channel_id, channel_name
                        )
                        
                        if doc:
                            yield doc
                            
                            # Fetch thread replies if configured
                            if self.options.get("include_threads", True):
                                thread_ts = message.get("thread_ts") or message.get("ts")
                                reply_count = message.get("reply_count", 0)
                                
                                if reply_count > 0:
                                    async for reply in self._fetch_thread(
                                        channel_id, thread_ts, channel_name
                                    ):
                                        yield reply
                    
                    # Check for more messages
                    cursor = response.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break
                
                except SlackApiError as e:
                    logger.error(
                        "Failed to fetch Slack messages",
                        channel_id=channel_id,
                        error=e.response["error"],
                    )
                    break
    
    async def fetch_updates(self, since: datetime) -> AsyncIterator[Dict[str, Any]]:
        """Fetch messages since timestamp."""
        client = self._get_client()
        oldest = str(since.timestamp())
        
        for channel_id in self.channel_ids:
            logger.info(
                "Fetching Slack updates",
                channel_id=channel_id,
                since=since.isoformat(),
            )
            
            try:
                channel_info = await client.conversations_info(channel=channel_id)
                channel_name = channel_info["channel"]["name"]
            except SlackApiError:
                channel_name = channel_id
            
            cursor = None
            
            while True:
                try:
                    response = await client.conversations_history(
                        channel=channel_id,
                        cursor=cursor,
                        oldest=oldest,
                        limit=200,
                    )
                    
                    messages = response.get("messages", [])
                    
                    for message in messages:
                        if message.get("subtype") == "bot_message":
                            continue
                        
                        text = message.get("text", "")
                        min_length = self.options.get("min_message_length", 10)
                        if len(text) < min_length:
                            continue
                        
                        doc = await self._parse_message(
                            message, channel_id, channel_name
                        )
                        
                        if doc:
                            yield doc
                    
                    cursor = response.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break
                
                except SlackApiError as e:
                    logger.error(
                        "Failed to fetch Slack updates",
                        error=e.response["error"],
                    )
                    break
    
    async def _fetch_thread(
        self,
        channel_id: str,
        thread_ts: str,
        channel_name: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Fetch thread replies."""
        client = self._get_client()
        
        try:
            response = await client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=100,
            )
            
            messages = response.get("messages", [])[1:]  # Skip parent
            
            for message in messages:
                doc = await self._parse_message(
                    message, channel_id, channel_name, is_thread=True
                )
                if doc:
                    yield doc
        
        except SlackApiError as e:
            logger.warning(
                "Failed to fetch thread",
                thread_ts=thread_ts,
                error=e.response["error"],
            )
    
    async def _parse_message(
        self,
        message: Dict[str, Any],
        channel_id: str,
        channel_name: str,
        is_thread: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Parse Slack message into document format."""
        ts = message.get("ts", "")
        text = message.get("text", "")
        
        if not text.strip():
            return None
        
        # Resolve user mentions
        content = await self.parse_content(text)
        
        # Get user name
        user_id = message.get("user", "")
        user_name = await self._get_user_name(user_id)
        
        # Create external ID
        external_id = f"{channel_id}-{ts}"
        
        # Create title from first line or truncated content
        title = content.split("\n")[0][:100]
        if len(title) < len(content.split("\n")[0]):
            title += "..."
        
        # Metadata
        metadata = self.get_metadata(message)
        metadata.update({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "user_id": user_id,
            "user_name": user_name,
            "is_thread": is_thread,
        })
        
        # Timestamp to datetime
        created_at = datetime.fromtimestamp(float(ts))
        
        return {
            "external_id": external_id,
            "title": title,
            "content": f"[{user_name}]: {content}",
            "url": f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
            "metadata": metadata,
            "created_at": created_at,
            "updated_at": created_at,
        }
    
    async def _get_user_name(self, user_id: str) -> str:
        """Get user display name with caching."""
        if not user_id:
            return "Unknown"
        
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        
        try:
            client = self._get_client()
            response = await client.users_info(user=user_id)
            
            user = response.get("user", {})
            name = (
                user.get("real_name")
                or user.get("profile", {}).get("display_name")
                or user.get("name")
                or user_id
            )
            
            self._user_cache[user_id] = name
            return name
        
        except SlackApiError:
            return user_id
    
    async def parse_content(self, raw_content: Any) -> str:
        """Process Slack message text."""
        if not raw_content:
            return ""
        
        text = str(raw_content)
        
        # Replace user mentions
        user_pattern = re.compile(r"<@([A-Z0-9]+)>")
        
        async def replace_user(match):
            user_id = match.group(1)
            name = await self._get_user_name(user_id)
            return f"@{name}"
        
        # Synchronous replacement with cached values
        for match in user_pattern.finditer(text):
            user_id = match.group(1)
            name = await self._get_user_name(user_id)
            text = text.replace(match.group(0), f"@{name}")
        
        # Replace channel mentions
        text = re.sub(r"<#([A-Z0-9]+)\|([^>]+)>", r"#\2", text)
        
        # Replace URLs
        text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2 (\1)", text)
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
        
        # Handle special characters
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        
        return text.strip()
    
    def get_metadata(self, raw_doc: Any) -> Dict[str, Any]:
        """Extract metadata from Slack message."""
        return {
            "ts": raw_doc.get("ts"),
            "thread_ts": raw_doc.get("thread_ts"),
            "reply_count": raw_doc.get("reply_count", 0),
            "reactions": [
                {"name": r.get("name"), "count": r.get("count")}
                for r in raw_doc.get("reactions", [])
            ],
            "attachments_count": len(raw_doc.get("attachments", [])),
            "files_count": len(raw_doc.get("files", [])),
        }
