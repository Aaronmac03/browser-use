"""
Configuration settings for the browser agent application.

This module defines the Settings class that manages all configuration options
for the browser automation system, including API keys, model settings, and
browser configuration.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Keys
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    serper_api_key: Optional[str] = Field(None, env="SERPER_API_KEY")
    
    # Model Configuration
    default_model: str = Field("gpt-4o", env="DEFAULT_MODEL")
    fallback_model: str = Field("ollama/llama3.2", env="FALLBACK_MODEL")
    ollama_base_url: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    
    # Browser Configuration
    headless: bool = Field(True, env="HEADLESS")
    browser_timeout: int = Field(30000, env="BROWSER_TIMEOUT")
    screenshot_on_error: bool = Field(True, env="SCREENSHOT_ON_ERROR")
    user_data_dir: str = Field("./user_data", env="USER_DATA_DIR")
    
    # Logging Configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("./logs/browser-agent.log", env="LOG_FILE")
    
    # Task Configuration
    max_retries: int = Field(3, env="MAX_RETRIES")
    task_timeout: int = Field(300, env="TASK_TIMEOUT")
    
    # Workflow Configuration
    enable_parallel_execution: bool = Field(False, env="ENABLE_PARALLEL_EXECUTION")
    max_concurrent_tasks: int = Field(2, env="MAX_CONCURRENT_TASKS")
    
    # Development Configuration
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("production", env="ENVIRONMENT")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        """Initialize settings and create necessary directories."""
        super().__init__(**kwargs)
        self._create_directories()
    
    def _create_directories(self):
        """Create necessary directories if they don't exist."""
        directories = [
            Path(self.user_data_dir),
            Path(self.log_file).parent,
            Path("screenshots"),
            Path("downloads"),
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() in ("development", "dev", "local")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() in ("production", "prod")
    
    def get_model_config(self) -> dict:
        """Get model configuration dictionary."""
        return {
            "default_model": self.default_model,
            "fallback_model": self.fallback_model,
            "ollama_base_url": self.ollama_base_url,
            "openai_api_key": self.openai_api_key,
            "anthropic_api_key": self.anthropic_api_key,
        }
    
    def get_browser_config(self) -> dict:
        """Get browser configuration dictionary."""
        return {
            "headless": self.headless,
            "timeout": self.browser_timeout,
            "screenshot_on_error": self.screenshot_on_error,
            "user_data_dir": self.user_data_dir,
        }