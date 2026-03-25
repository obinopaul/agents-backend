from pydantic_settings import BaseSettings
from typing import Literal, Optional


class StorageConfig(BaseSettings):
    """
    Configuration for cloud storage providers.
    
    Supports both GCS and S3-compatible storage backends.
    Set storage_provider to select which backend to use.
    """
    
    # Provider selection: 'gcs' or 's3'
    storage_provider: Literal["gcs", "s3"] = "gcs"
    
    # GCS settings (required if storage_provider='gcs')
    gcs_bucket_name: str = ""
    gcs_project_id: str = ""
    
    # S3 settings (required if storage_provider='s3')
    s3_bucket: str = ""
    s3_endpoint_url: str = ""  # Required for non-AWS (MinIO, Supabase, etc.)
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_public_url_base: str = ""  # Optional: CDN or public URL base