from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str

    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str | None = None

    llm_model: str = "claude-sonnet-4-6"
    embedding_model: str = "text-embedding-3-small"

    default_chunk_size_tokens: int = 500
    default_chunk_overlap_tokens: int = 50

    default_response_language: str = "en"

    max_upload_size_mb: int = 10

    log_level: str = "INFO"


settings = Settings()
