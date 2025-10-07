"""Application configuration management."""
from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    # Application settings
    DEBUG: bool = Field(default=False, description="Debug mode")
    SECRET_KEY: str = Field(..., description="Secret key for JWT tokens")
    ALLOWED_HOSTS: List[str] = Field(default=["*"], description="Allowed CORS origins")
    
    # ServiceNow settings
    SERVICE_NOW_REST_API_URL: str = Field(..., description="ServiceNow REST API URL")
    SERVICE_NOW_USER: str = Field(..., description="ServiceNow username")
    SERVICE_NOW_PASSWORD: str = Field(..., description="ServiceNow password")
    SERVICENOW_TIMEOUT: int = Field(default=30, description="ServiceNow API timeout")
    
    # OpenAI settings
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    OPENAI_MODEL: str = Field(default="gpt-4", description="OpenAI model to use")
    OPENAI_MAX_TOKENS: int = Field(default=1000, description="Max tokens for OpenAI response")
    
    # Security settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT token expiration")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    
    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format (json or console)")


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
