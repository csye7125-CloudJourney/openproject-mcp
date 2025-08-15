"""Config for the OpenProject MCP server."""

import os
import logging
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv


class OpenProjectConfig(BaseModel):
    """OpenProject API config."""
    
    base_url: str = Field(..., description="OpenProject instance URL")
    api_key: str = Field(..., description="OpenProject API key")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    
    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('base_url must start with http:// or https://')
        return v.rstrip('/')
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if not v or not v.strip():
            raise ValueError('api_key cannot be empty')
        return v.strip()
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v):
        if v <= 0:
            raise ValueError('timeout must be greater than 0')
        return v


class LoggingConfig(BaseModel):
    """Logging config."""
    
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json or text)")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f'level must be one of: {", ".join(valid_levels)}')
        return v.upper()
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        if v not in ["json", "text"]:
            raise ValueError('format must be either "json" or "text"')
        return v


class Config(BaseModel):
    """Top-level config for the MCP server."""

    openproject: OpenProjectConfig
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from env vars."""
        # pull from .env if present
        load_dotenv()

        # required
        base_url = os.getenv("OPENPROJECT_BASE_URL")
        api_key = os.getenv("OPENPROJECT_API_KEY")
        
        if not base_url:
            raise ValueError("OPENPROJECT_BASE_URL environment variable is required")
        if not api_key:
            raise ValueError("OPENPROJECT_API_KEY environment variable is required")
        
        return cls(
            openproject=OpenProjectConfig(
                base_url=base_url,
                api_key=api_key,
                timeout=int(os.getenv("OPENPROJECT_TIMEOUT", "30")),
                verify_ssl=os.getenv("OPENPROJECT_VERIFY_SSL", "true").lower() == "true"
            ),
            logging=LoggingConfig(
                level=os.getenv("LOG_LEVEL", "INFO"),
                format=os.getenv("LOG_FORMAT", "json")
            )
        )


def load_config() -> Config:
    """Load + validate config."""
    try:
        config = Config.from_env()
        logging.info("config loaded")
        return config
    except Exception as e:
        logging.error(f"failed to load config: {e}")
        raise