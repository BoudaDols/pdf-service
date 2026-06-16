from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # MySQL
    db_host: str = "pdf-service-mysql"
    db_port: int = 3306
    db_database: str = "pdf_service"
    db_username: str = "root"
    db_password: str = "secret"

    # Redis
    redis_host: str = "pdf-service-redis"
    redis_port: int = 6379

    # Storage backend: "s3" or "azure"
    storage_backend: str = "s3"

    # S3
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Azure Blob
    azure_storage_connection_string: str = ""
    azure_container_name: str = "pdfs"

    # Pre-signed URL expiration (seconds)
    presigned_url_ttl: int = 1800  # 30 minutes


settings = Settings()
