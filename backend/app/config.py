from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with Pydantic validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Allow extra env vars without error
    )

    # Application
    app_name: str = "Contract Intelligence MVP"
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = True  # Use JSON format for logs (set False for plain text)

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/contracts",
        description="PostgreSQL connection string",
    )
    # These are used by docker-compose, not directly by the app
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "contracts"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8100
    chroma_auth_token: str = "dev-token"

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = "gpt-4o"

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_base_url: str = "https://cloud.langfuse.com"  # Alias for langfuse_host

    # JWT Authentication
    jwt_secret_key: str = Field(
        default="CHANGE-THIS-SECRET-IN-PRODUCTION",
        description="Secret key for JWT encoding",
    )
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    access_token_expire_minutes: int = 30  # Alternative config option

    # CORS - allow all origins for demo/dev (restrict in production)
    cors_origins: list[str] = ["*"]

    # File Upload
    max_upload_size_mb: int = 50
    upload_dir: str = "data/uploads"
    processed_dir: str = "data/processed"

    @property
    def effective_langfuse_host(self) -> str:
        """Get the effective Langfuse host URL."""
        return self.langfuse_base_url or self.langfuse_host


settings = Settings()
