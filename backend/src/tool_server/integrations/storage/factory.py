"""Storage client factory for creating appropriate storage backends."""

from .config import StorageConfig
from .base import BaseStorage
from .gcs import GCS
from .s3 import S3Storage


def create_storage_client(config: StorageConfig) -> BaseStorage:
    """
    Create a storage client based on configuration.
    
    Args:
        config: StorageConfig instance with provider settings
        
    Returns:
        BaseStorage implementation (GCS or S3Storage)
        
    Raises:
        ValueError: If storage provider is not supported or config is invalid
    """
    if config.storage_provider == "gcs":
        if not config.gcs_project_id or not config.gcs_bucket_name:
            raise ValueError(
                "GCS storage requires gcs_project_id and gcs_bucket_name"
            )
        return GCS(
            project_id=config.gcs_project_id,
            bucket_name=config.gcs_bucket_name,
        )
    
    elif config.storage_provider == "s3":
        if not config.s3_bucket:
            raise ValueError("S3 storage requires s3_bucket")
        return S3Storage(
            bucket=config.s3_bucket,
            endpoint_url=config.s3_endpoint_url or None,
            region=config.s3_region,
            access_key=config.s3_access_key or None,
            secret_key=config.s3_secret_key or None,
            public_url_base=config.s3_public_url_base or None,
        )
    
    raise ValueError(f"Storage provider '{config.storage_provider}' not supported")