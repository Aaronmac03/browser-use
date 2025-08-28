"""
Browser Profile Manager for handling different browser profiles and security settings.

This module provides the BrowserProfileManager class that manages browser profiles
for different services and use cases, including security configurations and
profile persistence.
"""

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from pydantic import BaseModel, Field


class ProfileType(str, Enum):
    """Enumeration of supported browser profile types."""
    DEFAULT = "default"
    SOCIAL_MEDIA = "social_media"
    ECOMMERCE = "ecommerce"
    BANKING = "banking"
    DEVELOPMENT = "development"
    TESTING = "testing"


class SecurityLevel(str, Enum):
    """Security levels for browser profiles."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAXIMUM = "maximum"


@dataclass
class SecuritySettings:
    """Security settings for browser profiles."""
    disable_javascript: bool = False
    disable_images: bool = False
    disable_plugins: bool = True
    disable_extensions: bool = False
    block_ads: bool = True
    block_trackers: bool = True
    enable_incognito: bool = False
    clear_cookies_on_exit: bool = False
    disable_webgl: bool = False
    disable_webrtc: bool = False
    user_agent_override: Optional[str] = None
    proxy_settings: Optional[Dict[str, str]] = None
    allowed_domains: Optional[List[str]] = None
    blocked_domains: Optional[List[str]] = None


@dataclass
class BrowserProfile:
    """Browser profile configuration."""
    name: str
    profile_type: ProfileType
    security_level: SecurityLevel
    security_settings: SecuritySettings
    user_data_dir: str
    created_at: datetime
    last_used: Optional[datetime] = None
    description: Optional[str] = None
    custom_settings: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_used'] = self.last_used.isoformat() if self.last_used else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrowserProfile':
        """Create profile from dictionary."""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('last_used'):
            data['last_used'] = datetime.fromisoformat(data['last_used'])
        
        security_settings_data = data.pop('security_settings')
        security_settings = SecuritySettings(**security_settings_data)
        
        return cls(
            security_settings=security_settings,
            **data
        )


class BrowserProfileManager:
    """Manager for browser profiles with security configurations."""

    def __init__(self, profiles_dir: str = "./profiles"):
        """
        Initialize the browser profile manager.
        
        Args:
            profiles_dir: Directory to store profile configurations
        """
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_file = self.profiles_dir / "profiles.json"
        self.logger = logging.getLogger(__name__)
        
        # Load existing profiles
        self._profiles: Dict[str, BrowserProfile] = {}
        self._load_profiles()

    def create_profile(
        self,
        name: str,
        profile_type: ProfileType,
        security_level: SecurityLevel = SecurityLevel.MEDIUM,
        description: Optional[str] = None,
        custom_settings: Optional[Dict[str, Any]] = None
    ) -> BrowserProfile:
        """
        Create a new browser profile.
        
        Args:
            name: Profile name (must be unique)
            profile_type: Type of profile
            security_level: Security level for the profile
            description: Optional description
            custom_settings: Custom browser settings
            
        Returns:
            Created browser profile
            
        Raises:
            ValueError: If profile name already exists
        """
        if name in self._profiles:
            raise ValueError(f"Profile '{name}' already exists")

        # Generate security settings based on level and type
        security_settings = self._generate_security_settings(security_level, profile_type)
        
        # Create user data directory
        user_data_dir = str(self.profiles_dir / f"profile_{name}")
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)

        profile = BrowserProfile(
            name=name,
            profile_type=profile_type,
            security_level=security_level,
            security_settings=security_settings,
            user_data_dir=user_data_dir,
            created_at=datetime.now(),
            description=description,
            custom_settings=custom_settings or {}
        )

        self._profiles[name] = profile
        self._save_profiles()
        
        self.logger.info(f"Created browser profile: {name} ({profile_type.value})")
        return profile

    def get_profile(self, name: str) -> Optional[BrowserProfile]:
        """
        Get a browser profile by name.
        
        Args:
            name: Profile name
            
        Returns:
            Browser profile or None if not found
        """
        profile = self._profiles.get(name)
        if profile:
            profile.last_used = datetime.now()
            self._save_profiles()
        return profile

    def list_profiles(self) -> List[BrowserProfile]:
        """
        List all available browser profiles.
        
        Returns:
            List of browser profiles
        """
        return list(self._profiles.values())

    def delete_profile(self, name: str) -> bool:
        """
        Delete a browser profile.
        
        Args:
            name: Profile name
            
        Returns:
            True if profile was deleted, False if not found
        """
        if name not in self._profiles:
            return False

        profile = self._profiles[name]
        
        # Remove user data directory
        user_data_path = Path(profile.user_data_dir)
        if user_data_path.exists():
            import shutil
            shutil.rmtree(user_data_path)

        del self._profiles[name]
        self._save_profiles()
        
        self.logger.info(f"Deleted browser profile: {name}")
        return True

    def update_profile(
        self,
        name: str,
        security_level: Optional[SecurityLevel] = None,
        description: Optional[str] = None,
        custom_settings: Optional[Dict[str, Any]] = None
    ) -> Optional[BrowserProfile]:
        """
        Update an existing browser profile.
        
        Args:
            name: Profile name
            security_level: New security level
            description: New description
            custom_settings: New custom settings
            
        Returns:
            Updated profile or None if not found
        """
        if name not in self._profiles:
            return None

        profile = self._profiles[name]
        
        if security_level:
            profile.security_level = security_level
            profile.security_settings = self._generate_security_settings(
                security_level, profile.profile_type
            )
        
        if description is not None:
            profile.description = description
            
        if custom_settings is not None:
            profile.custom_settings = custom_settings

        self._save_profiles()
        self.logger.info(f"Updated browser profile: {name}")
        return profile

    def get_browser_config(self, profile_name: str) -> Dict[str, Any]:
        """
        Get browser configuration for a specific profile.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            Browser configuration dictionary
            
        Raises:
            ValueError: If profile not found
        """
        profile = self.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")

        config = {
            "user_data_dir": profile.user_data_dir,
            "headless": profile.custom_settings.get("headless", True),
            "args": self._get_browser_args(profile),
        }

        # Add proxy settings if configured
        if profile.security_settings.proxy_settings:
            config["proxy"] = profile.security_settings.proxy_settings

        return config

    def _generate_security_settings(
        self, 
        security_level: SecurityLevel, 
        profile_type: ProfileType
    ) -> SecuritySettings:
        """Generate security settings based on level and profile type."""
        settings = SecuritySettings()

        # Base security settings by level
        if security_level == SecurityLevel.LOW:
            settings.block_ads = False
            settings.block_trackers = False
        elif security_level == SecurityLevel.MEDIUM:
            settings.block_ads = True
            settings.block_trackers = True
        elif security_level == SecurityLevel.HIGH:
            settings.block_ads = True
            settings.block_trackers = True
            settings.disable_plugins = True
            settings.disable_webgl = True
        elif security_level == SecurityLevel.MAXIMUM:
            settings.block_ads = True
            settings.block_trackers = True
            settings.disable_plugins = True
            settings.disable_webgl = True
            settings.disable_webrtc = True
            settings.enable_incognito = True
            settings.clear_cookies_on_exit = True

        # Profile-specific adjustments
        if profile_type == ProfileType.BANKING:
            settings.disable_extensions = True
            settings.enable_incognito = True
            settings.clear_cookies_on_exit = True
        elif profile_type == ProfileType.DEVELOPMENT:
            settings.disable_javascript = False
            settings.disable_images = False
            settings.block_ads = False
        elif profile_type == ProfileType.TESTING:
            settings.disable_images = True
            settings.block_ads = True

        return settings

    def _get_browser_args(self, profile: BrowserProfile) -> List[str]:
        """Generate browser arguments based on profile settings."""
        args = []
        settings = profile.security_settings

        if settings.disable_javascript:
            args.append("--disable-javascript")
        
        if settings.disable_images:
            args.append("--disable-images")
            
        if settings.disable_plugins:
            args.append("--disable-plugins")
            
        if settings.disable_extensions:
            args.append("--disable-extensions")
            
        if settings.disable_webgl:
            args.append("--disable-webgl")
            
        if settings.disable_webrtc:
            args.append("--disable-webrtc")

        if settings.enable_incognito:
            args.append("--incognito")

        if settings.user_agent_override:
            args.append(f"--user-agent={settings.user_agent_override}")

        # Security-focused arguments
        args.extend([
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
        ])

        return args

    def _load_profiles(self):
        """Load profiles from disk."""
        if not self.profiles_file.exists():
            return

        try:
            with open(self.profiles_file, 'r') as f:
                data = json.load(f)
                
            for profile_data in data.get('profiles', []):
                profile = BrowserProfile.from_dict(profile_data)
                self._profiles[profile.name] = profile
                
            self.logger.info(f"Loaded {len(self._profiles)} browser profiles")
        except Exception as e:
            self.logger.error(f"Failed to load profiles: {e}")

    def _save_profiles(self):
        """Save profiles to disk."""
        try:
            data = {
                'profiles': [profile.to_dict() for profile in self._profiles.values()],
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.profiles_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save profiles: {e}")