import os

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
    # "demo" keeps legacy open endpoints; "enterprise" enforces auth on them
    security_profile: str = "demo"
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
    # Per-request timeout (seconds) and retry budget for every OpenAI/Azure
    # client the factory builds. Without these the SDK defaults to a very long
    # timeout and can hang the extraction pipeline on a stalled connection.
    openai_timeout_seconds: float = Field(
        default=120.0, description="Per-request timeout for OpenAI/Azure calls"
    )
    openai_max_retries: int = Field(
        default=3, description="SDK-level retry budget for OpenAI/Azure calls"
    )
    # Cell-level residency overrides (data-residency cells, e.g. the EU cell).
    # openai_base_url points the global OpenAI client at an OpenAI-compatible
    # regional endpoint; the azure_* trio routes ALL tenants without their own
    # AI config through a cell-level Azure OpenAI resource (deployments must be
    # named after the model ids, same rule as per-tenant Azure).
    openai_base_url: str = Field(
        default="", description="Override base URL for the global OpenAI client"
    )
    azure_openai_endpoint: str = Field(
        default="", description="Cell-level Azure OpenAI endpoint (residency default)"
    )
    azure_openai_api_key: str = Field(
        default="", description="Key for the cell-level Azure endpoint (falls back to openai_api_key)"
    )
    azure_openai_api_version: str = Field(
        default="", description="API version for the cell-level Azure endpoint"
    )

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

    # Public URL (used for email links to external portal)
    public_url: str = Field(
        default="http://localhost:3000",
        description="Public-facing URL of the frontend app (e.g. http://52.21.204.211)",
    )

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

# docker-compose passes the residency overrides as ${VAR:-}, i.e. an EMPTY
# string when unset. The OpenAI SDK reads OPENAI_BASE_URL from the environment
# at client construction and treats "" as a real base URL — every request then
# dies with "Request URL is missing an 'http://' or 'https://' protocol".
# Scrub empty values here (config is imported before any client is built);
# Settings above already treat "" as unset.
for _var in (
    "OPENAI_BASE_URL",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
):
    if os.environ.get(_var) == "":
        del os.environ[_var]
