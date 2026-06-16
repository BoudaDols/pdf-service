import boto3
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, timezone
from app.config import settings


def get_presigned_url(filename: str) -> str:
    """
    Generate a time-limited pre-signed URL for downloading a PDF.
    Uses S3 or Azure Blob depending on STORAGE_BACKEND config.
    """
    if settings.storage_backend == "azure":
        return _azure_presigned_url(filename)
    return _s3_presigned_url(filename)


def _s3_presigned_url(filename: str) -> str:
    """Generate an S3 pre-signed GET URL."""
    client = boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": filename},
        ExpiresIn=settings.presigned_url_ttl,
    )
    return url


def _azure_presigned_url(filename: str) -> str:
    """Generate an Azure Blob SAS URL."""
    blob_service = BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )
    account_name = blob_service.account_name

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=settings.azure_container_name,
        blob_name=filename,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(seconds=settings.presigned_url_ttl),
    )

    url = (
        f"https://{account_name}.blob.core.windows.net/"
        f"{settings.azure_container_name}/{filename}?{sas_token}"
    )
    return url
