#!/usr/bin/env python3
"""
Configuration Manager for Splunk Skills

Provides multi-source configuration management with profile support.
Configuration priority (highest to lowest):
    1. Environment variables
    2. .claude/settings.local.json (personal, gitignored)
    3. .claude/settings.json (team defaults)
    4. Built-in defaults

Environment Variables:
    SPLUNK_TOKEN - JWT Bearer token (preferred auth)
    SPLUNK_USERNAME - Username for Basic Auth
    SPLUNK_PASSWORD - Password for Basic Auth
    SPLUNK_SITE_URL - Splunk host URL
    SPLUNK_MANAGEMENT_PORT - Management port (default: 8089)
    SPLUNK_PROFILE - Profile name to use
    SPLUNK_VERIFY_SSL - SSL verification (true/false)
    SPLUNK_DEFAULT_APP - Default app context
    SPLUNK_DEFAULT_INDEX - Default search index
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from assistant_skills_lib.config_manager import BaseConfigManager
from .error_handler import ValidationError
from .splunk_client import SplunkClient


class ConfigManager(BaseConfigManager):
    """Manages Splunk configuration from multiple sources, inheriting from BaseConfigManager."""

    def __init__(self, profile: Optional[str] = None):
        """
        Initialize the configuration manager.

        Args:
            profile: Profile name to use. If not provided,
                       searches for default from env or settings files.
        """
        super().__init__(profile=profile)

    def get_service_name(self) -> str:
        """Returns the name of the service, which is 'splunk'."""
        return "splunk"

    def get_default_config(self) -> Dict[str, Any]:
        """Returns the default configuration dictionary for Splunk."""
        return {
            "default_profile": "default",
            "profiles": {
                "default": {
                    "url": "",
                    "port": 8089,
                    "auth_method": "bearer",
                    "default_app": "search",
                    "default_index": "main",
                    "verify_ssl": True,
                    "deployment_type": "on-prem",
                }
            },
            "api": {
                "timeout": 30,
                "search_timeout": 300,
                "max_retries": 3,
                "retry_backoff": 2.0,
                "default_output_mode": "json",
                "prefer_v2_api": True,
            },
            "search_defaults": {
                "earliest_time": "-24h",
                "latest_time": "now",
                "max_count": 50000,
                "status_buckets": 300,
                "auto_cancel": 300,
            },
        }



    def get_profile_config(self, profile_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration for a specific profile, merged with defaults and environment variables.

        Args:
            profile_name: Profile name (uses default if not specified)

        Returns:
            Profile configuration dictionary
        """
        # Determine profile to use
        profile_to_use = profile_name or self.profile
        
        # Get base config from files
        base_profile = super().get_profile_config(profile_to_use)

        # Merge with default profile if not the default
        default_profile_config = self.config.get(self.service_name, {}).get("profiles", {}).get("default", {})
        if profile_to_use != "default":
            merged_profile = self._deep_merge(default_profile_config, base_profile)
        else:
            merged_profile = base_profile

        # Apply environment variable overrides
        env_overrides = self._get_env_overrides()
        final_profile = self._deep_merge(merged_profile, env_overrides)

        # Add API and search defaults
        final_profile["api"] = self.get_api_config()
        final_profile["search_defaults"] = self.config.get(self.service_name, {}).get("search_defaults", {})

        return final_profile

    def _get_env_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables."""
        overrides: Dict[str, Any] = {}
        
        if url := self.get_credential_from_env("SITE_URL"): overrides["url"] = url
        if port := self.get_credential_from_env("MANAGEMENT_PORT"):
            try: overrides["port"] = int(port)
            except ValueError: pass
        if token := self.get_credential_from_env("TOKEN"):
            overrides["token"] = token
            overrides["auth_method"] = "bearer"
        if username := self.get_credential_from_env("USERNAME"): overrides["username"] = username
        if password := self.get_credential_from_env("PASSWORD"):
            overrides["password"] = password
            if not overrides.get("token"): overrides["auth_method"] = "basic"
        if verify_ssl := self.get_credential_from_env("VERIFY_SSL"): overrides["verify_ssl"] = verify_ssl.lower() in ("true", "1", "yes")
        if default_app := self.get_credential_from_env("DEFAULT_APP"): overrides["default_app"] = default_app
        if default_index := self.get_credential_from_env("DEFAULT_INDEX"): overrides["default_index"] = default_index

        return overrides

    def get_client_kwargs(self, profile_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get keyword arguments for SplunkClient initialization.
        """
        profile = self.get_profile_config(profile_name)
        api_config = profile.get("api", {})

        kwargs: Dict[str, Any] = {
            "base_url": profile.get("url", ""),
            "port": profile.get("port", 8089),
            "timeout": api_config.get("timeout", 30),
            "verify_ssl": profile.get("verify_ssl", True),
            "max_retries": api_config.get("max_retries", 3),
            "retry_backoff": api_config.get("retry_backoff", 2.0),
        }

        auth_method = profile.get("auth_method", "bearer")
        if auth_method == "bearer" and profile.get("token"):
            kwargs["token"] = profile["token"]
        elif profile.get("username") and profile.get("password"):
            kwargs["username"] = profile["username"]
            kwargs["password"] = profile["password"]
        elif profile.get("token"):
            kwargs["token"] = profile["token"]

        return kwargs

    def validate_config(self, profile_name: Optional[str] = None) -> list:
        """
        Validate configuration and return list of issues.
        """
        errors = []
        profile = self.get_profile_config(profile_name)

        if not profile.get("url"):
            errors.append("Missing Splunk URL. Set SPLUNK_SITE_URL or configure in settings.json")
        
        auth_method = profile.get("auth_method", "bearer")
        if auth_method == "bearer" and not profile.get("token"):
            errors.append("Missing Splunk token. Set SPLUNK_TOKEN or configure in settings.local.json")
        elif auth_method != "bearer" and not (profile.get("username") and profile.get("password")):
            errors.append("Missing Splunk username/password for basic auth. Set SPLUNK_USERNAME and SPLUNK_PASSWORD or configure in settings.local.json")
        
        return errors

# Global config manager instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """Get or create global ConfigManager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager.get_instance()
    return _config_manager


def get_config(profile: Optional[str] = None) -> Dict[str, Any]:
    """
    Get configuration for specified profile.
    """
    return get_config_manager().get_profile_config(profile)


def get_splunk_client(profile: Optional[str] = None) -> SplunkClient:
    """
    Create SplunkClient instance from configuration.
    """
    manager = get_config_manager()
    errors = manager.validate_config(profile)
    if errors:
        raise ValidationError("\n".join(errors))
    kwargs = manager.get_client_kwargs(profile)
    return SplunkClient(**kwargs)


def get_search_defaults(profile: Optional[str] = None) -> Dict[str, Any]:
    """
    Get search default settings.
    """
    config = get_config(profile)
    return config.get("search_defaults", {})


def get_api_settings(profile: Optional[str] = None) -> Dict[str, Any]:
    """
    Get API settings.
    """
    config = get_config(profile)
    return config.get("api", {})
