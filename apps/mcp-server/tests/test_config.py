"""Test configuration loading and validation."""

import os
import pytest
from unittest.mock import patch

from openproject_mcp_server.config import Config


class TestConfig:
    """Test configuration loading and validation."""
    
    def test_load_config_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            'OPENPROJECT_BASE_URL': 'https://openproject.example.com',
            'OPENPROJECT_API_KEY': 'test-api-key',
            'OPENPROJECT_TIMEOUT': '45',
            'LOG_LEVEL': 'DEBUG'
        }):
            config = Config.from_env()
            
            assert config.openproject.base_url == 'https://openproject.example.com'
            assert config.openproject.api_key == 'test-api-key'
            assert config.openproject.timeout == 45
            assert config.logging.level == 'DEBUG'
    
    def test_load_config_defaults(self):
        """Test loading configuration with default values."""
        with patch.dict(os.environ, {
            'OPENPROJECT_BASE_URL': 'https://openproject.example.com',
            'OPENPROJECT_API_KEY': 'test-api-key'
        }, clear=True):
            config = Config.from_env()
            
            assert config.openproject.timeout == 30
            assert config.openproject.verify_ssl == True
            assert config.logging.level == 'INFO'
            assert config.logging.format == 'json'
    
    def test_missing_required_env_vars(self):
        """Test that missing required environment variables raise ValueError."""
        # Clear all environment variables and ensure no .env file is loaded
        with patch.dict(os.environ, {}, clear=True):
            with patch('openproject_mcp_server.config.load_dotenv'):  # Prevent .env loading
                with pytest.raises(ValueError, match="OPENPROJECT_BASE_URL environment variable is required"):
                    Config.from_env()
    
    def test_invalid_base_url(self):
        """Test that invalid base URL raises ValueError."""
        with patch.dict(os.environ, {
            'OPENPROJECT_BASE_URL': 'invalid-url',
            'OPENPROJECT_API_KEY': 'test-api-key'
        }):
            with pytest.raises(ValueError, match="base_url must start with http"):
                Config.from_env()
    
    def test_invalid_timeout(self):
        """Test that invalid timeout raises ValueError."""
        with patch.dict(os.environ, {
            'OPENPROJECT_BASE_URL': 'https://openproject.example.com',
            'OPENPROJECT_API_KEY': 'test-api-key',
            'OPENPROJECT_TIMEOUT': '0'
        }):
            with pytest.raises(ValueError, match="timeout must be greater than 0"):
                Config.from_env()
    
    def test_invalid_log_level(self):
        """Test that invalid log level raises ValueError."""
        with patch.dict(os.environ, {
            'OPENPROJECT_BASE_URL': 'https://openproject.example.com',
            'OPENPROJECT_API_KEY': 'test-api-key',
            'LOG_LEVEL': 'INVALID'
        }):
            with pytest.raises(ValueError, match="level must be one of"):
                Config.from_env()
    
    def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base URL."""
        with patch.dict(os.environ, {
            'OPENPROJECT_BASE_URL': 'https://openproject.example.com/',
            'OPENPROJECT_API_KEY': 'test-api-key'
        }):
            config = Config.from_env()
            assert config.openproject.base_url == 'https://openproject.example.com'