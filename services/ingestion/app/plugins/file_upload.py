"""
File upload integration plugin.

Supports: PDF, DOCX, TXT, MD, HTML
"""

import io
import os
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional

import boto3
import structlog
from botocore.config import Config

from app.config import settings
from .base import BaseIntegrationPlugin

logger = structlog.get_logger()


class FileUploadPlugin(BaseIntegrationPlugin):
    """Plugin for file upload integration."""
    
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.storage_config = config.get("storage", {})
        self.processing = config.get("processing", {})
        
        # S3 client configuration
        self._s3_client = None
    
    def _get_s3_client(self):
        """Get or create S3 client."""
        if self._s3_client is None:
            config = Config(
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3},
            )
            
            endpoint_url = (
                self.storage_config.get("endpoint")
                or settings.S3_ENDPOINT
                or None
            )
            
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=self.storage_config.get("region", settings.AWS_REGION),
                config=config,
            )
        
        return self._s3_client
    
    async def validate_config(self) -> bool:
        """Validate file upload configuration."""
        bucket = self.storage_config.get("bucket", settings.S3_BUCKET)
        if not bucket:
            raise ValueError("storage.bucket is required")
        
        # Test S3 access
        try:
            s3 = self._get_s3_client()
            s3.head_bucket(Bucket=bucket)
            return True
        except Exception as e:
            raise ValueError(f"Cannot access S3 bucket: {e}")
    
    async def fetch_initial(self) -> AsyncIterator[Dict[str, Any]]:
        """Fetch all files from S3 bucket."""
        s3 = self._get_s3_client()
        bucket = self.storage_config.get("bucket", settings.S3_BUCKET)
        prefix = self.storage_config.get("prefix", "uploads/")
        
        logger.info(
            "Fetching files from S3",
            bucket=bucket,
            prefix=prefix,
        )
        
        paginator = s3.get_paginator("list_objects_v2")
        
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                
                # Check extension
                ext = os.path.splitext(key)[1].lower()
                allowed = self.processing.get(
                    "allowed_extensions",
                    [".pdf", ".docx", ".txt", ".md"]
                )
                
                if ext not in allowed:
                    continue
                
                # Check file size
                max_size = self.processing.get("max_file_size_mb", 100) * 1024 * 1024
                if obj["Size"] > max_size:
                    logger.warning(
                        "File too large, skipping",
                        key=key,
                        size=obj["Size"],
                    )
                    continue
                
                try:
                    doc = await self._process_file(s3, bucket, obj)
                    if doc:
                        yield doc
                except Exception as e:
                    logger.error(
                        "Failed to process file",
                        key=key,
                        error=str(e),
                    )
    
    async def fetch_updates(self, since: datetime) -> AsyncIterator[Dict[str, Any]]:
        """Fetch files modified since timestamp."""
        s3 = self._get_s3_client()
        bucket = self.storage_config.get("bucket", settings.S3_BUCKET)
        prefix = self.storage_config.get("prefix", "uploads/")
        
        logger.info(
            "Fetching file updates",
            bucket=bucket,
            prefix=prefix,
            since=since.isoformat(),
        )
        
        paginator = s3.get_paginator("list_objects_v2")
        
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                # Check modification time
                last_modified = obj["LastModified"].replace(tzinfo=None)
                if last_modified < since:
                    continue
                
                key = obj["Key"]
                
                # Check extension
                ext = os.path.splitext(key)[1].lower()
                allowed = self.processing.get(
                    "allowed_extensions",
                    [".pdf", ".docx", ".txt", ".md"]
                )
                
                if ext not in allowed:
                    continue
                
                # Check file size
                max_size = self.processing.get("max_file_size_mb", 100) * 1024 * 1024
                if obj["Size"] > max_size:
                    continue
                
                try:
                    doc = await self._process_file(s3, bucket, obj)
                    if doc:
                        yield doc
                except Exception as e:
                    logger.error(
                        "Failed to process file",
                        key=key,
                        error=str(e),
                    )
    
    async def _process_file(
        self,
        s3,
        bucket: str,
        obj: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Download and process a file from S3."""
        key = obj["Key"]
        ext = os.path.splitext(key)[1].lower()
        
        # Download file
        response = s3.get_object(Bucket=bucket, Key=key)
        file_content = response["Body"].read()
        
        # Parse content based on extension
        content = await self._extract_text(file_content, ext)
        
        if not content or not content.strip():
            logger.warning("Empty content after extraction", key=key)
            return None
        
        # Create document
        filename = os.path.basename(key)
        
        return {
            "external_id": key,
            "title": filename,
            "content": content,
            "url": f"s3://{bucket}/{key}",
            "metadata": self.get_metadata({
                "key": key,
                "bucket": bucket,
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
                "content_type": response.get("ContentType"),
            }),
            "created_at": obj["LastModified"],
            "updated_at": obj["LastModified"],
        }
    
    async def _extract_text(self, content: bytes, ext: str) -> str:
        """Extract text from file based on extension."""
        if ext == ".txt":
            return content.decode("utf-8", errors="ignore")
        
        elif ext == ".md":
            return content.decode("utf-8", errors="ignore")
        
        elif ext in (".html", ".htm"):
            return await self._extract_html(content)
        
        elif ext == ".pdf":
            return await self._extract_pdf(content)
        
        elif ext == ".docx":
            return await self._extract_docx(content)
        
        return ""
    
    async def _extract_html(self, content: bytes) -> str:
        """Extract text from HTML."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(content, "lxml")
        
        # Remove scripts and styles
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line)
    
    async def _extract_pdf(self, content: bytes) -> str:
        """Extract text from PDF."""
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(io.BytesIO(content))
            text_parts = []
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
        
        except ImportError:
            logger.warning("PyPDF2 not installed, skipping PDF")
            return ""
        except Exception as e:
            logger.error("Failed to extract PDF", error=str(e))
            return ""
    
    async def _extract_docx(self, content: bytes) -> str:
        """Extract text from DOCX."""
        try:
            from docx import Document
            
            doc = Document(io.BytesIO(content))
            text_parts = []
            
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)
            
            return "\n\n".join(text_parts)
        
        except ImportError:
            logger.warning("python-docx not installed, skipping DOCX")
            return ""
        except Exception as e:
            logger.error("Failed to extract DOCX", error=str(e))
            return ""
    
    async def parse_content(self, raw_content: Any) -> str:
        """Parse content - already extracted by file processor."""
        return str(raw_content) if raw_content else ""
    
    def get_metadata(self, raw_doc: Any) -> Dict[str, Any]:
        """Extract metadata from file info."""
        return {
            "bucket": raw_doc.get("bucket"),
            "key": raw_doc.get("key"),
            "size_bytes": raw_doc.get("size"),
            "content_type": raw_doc.get("content_type"),
            "last_modified": str(raw_doc.get("last_modified")) if raw_doc.get("last_modified") else None,
        }
