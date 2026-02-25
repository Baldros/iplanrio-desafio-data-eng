from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # AWS / S3 / MinIO Config
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: Optional[str] = "http://minio:9000"
    
    # Bucket and Path
    BUCKET_NAME: str = "terceirizados"
    GOLD_PATH: str = "gold/terceirizados-gold.duckdb"
    
    # API Config
    API_PORT: int = 8000
    CACHE_EXPIRE_SECONDS: int = 3600 # 1 hora
    
    # Configuração para ler do .env se existir
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
