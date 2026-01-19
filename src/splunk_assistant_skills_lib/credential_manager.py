"""
Splunk Credential Management

Provides secure credential storage with keychain integration for Splunk Assistant Skills.
Extends BaseCredentialManager from assistant_skills_lib.

Priority order:
1. Environment variables (SPLUNK_TOKEN, SPLUNK_USERNAME, etc.)
2. System keychain (via keyring library)
3. .claude/settings.local.json
"""

from __future__ import annotations

from typing import Any

from assistant_skills_lib import BaseCredentialManager

from .splunk_client import SplunkClient


class SplunkCredentialManager(BaseCredentialManager):
    """
    Credential manager for Splunk Assistant Skills.

    Handles secure storage and retrieval of Splunk credentials including:
    - Site URL
    - Bearer token (preferred) or username/password
    - Port configuration

    Example usage:
        from splunk_assistant_skills_lib import SplunkCredentialManager

        # Get credentials
        manager = SplunkCredentialManager()
        creds = manager.get_credentials()

        # Store credentials
        manager.store_credentials({
            "site_url": "https://splunk.example.com",
            "token": "eyJr...",
            "port": "8089"
        })
    """

    def get_service_name(self) -> str:
        """Return the keychain service name."""
        return "splunk-assistant"

    def get_env_prefix(self) -> str:
        """Return the environment variable prefix."""
        return "SPLUNK"

    def get_credential_fields(self) -> list[str]:
        """Return list of credential field names.

        Required fields:
        - site_url: Splunk instance URL
        - token: JWT Bearer token (preferred auth)

        Optional fields (for basic auth fallback):
        - username: Splunk username
        - password: Splunk password
        - port: Management port (default: 8089)
        """
        return ["site_url", "token", "username", "password", "port"]

    def get_required_fields(self) -> list[str]:
        """Return list of required credential fields.

        Only site_url is truly required - authentication can be
        either token OR username+password.
        """
        return ["site_url"]

    def get_credential_not_found_hint(self) -> str:
        """Return help text for credential not found error."""
        return """To configure Splunk credentials, set environment variables:

  # Required
  export SPLUNK_SITE_URL='https://splunk.example.com'

  # Authentication (choose one method)
  # Option 1: Bearer token (preferred)
  export SPLUNK_TOKEN='eyJr...'

  # Option 2: Basic auth
  export SPLUNK_USERNAME='admin'
  export SPLUNK_PASSWORD='changeme'

  # Optional
  export SPLUNK_PORT='8089'

Or use the setup wizard: /splunk-assistant-setup
"""

    def validate_credentials(self, credentials: dict[str, str]) -> dict[str, Any]:
        """
        Validate credentials by making a test API call.

        Args:
            credentials: Dictionary of credential values

        Returns:
            Server info on success

        Raises:
            ValidationError: If site_url missing
            AuthenticationError: If credentials are invalid
        """
        from .error_handler import AuthenticationError, ValidationError

        site_url = credentials.get("site_url")
        if not site_url:
            raise ValidationError(
                "site_url is required",
                operation="validate_credentials",
            )

        # Get auth info
        token = credentials.get("token")
        username = credentials.get("username")
        password = credentials.get("password")
        port = int(credentials.get("port", "8089"))

        if not token and not (username and password):
            raise ValidationError(
                "Either token or username+password required",
                operation="validate_credentials",
            )

        try:
            # Create client and test connection
            client = SplunkClient(
                base_url=site_url,
                token=token,
                username=username,
                password=password,
                port=port,
                verify_ssl=True,
            )

            with client:
                server_info = client.get_server_info()

            return server_info

        except Exception as e:
            raise AuthenticationError(
                f"Failed to connect to Splunk: {e}",
                operation="validate_credentials",
            )

    def get_credentials(self) -> dict[str, str]:
        """
        Retrieve all credentials with flexible auth requirements.

        Unlike the base class, this allows either token OR username+password.

        Returns:
            Dictionary of credential field -> value

        Raises:
            CredentialNotFoundError: If minimum credentials not found
        """
        from assistant_skills_lib import CredentialNotFoundError

        fields = self.get_credential_fields()
        result: dict[str, str | None] = {field: None for field in fields}

        # Priority 1: Environment variables
        env_creds = self.get_credentials_from_env()
        for field, value in env_creds.items():
            if value:
                result[field] = value

        # Priority 2: Keychain
        if any(v is None for v in result.values()):
            kc_creds = self.get_credentials_from_keychain()
            for field, value in kc_creds.items():
                if result.get(field) is None and value:
                    result[field] = value

        # Priority 3: JSON file
        if any(v is None for v in result.values()):
            json_creds = self.get_credentials_from_json()
            for field, value in json_creds.items():
                if result.get(field) is None and value:
                    result[field] = value

        # Validate minimum requirements
        if not result.get("site_url"):
            raise CredentialNotFoundError(
                self.get_service_name(),
                hint=self.get_credential_not_found_hint(),
            )

        has_token = bool(result.get("token"))
        has_basic = bool(result.get("username") and result.get("password"))

        if not has_token and not has_basic:
            raise CredentialNotFoundError(
                self.get_service_name(),
                hint=self.get_credential_not_found_hint(),
            )

        # Return only non-None values
        return {k: v for k, v in result.items() if v is not None}


# Singleton instance
_credential_manager: SplunkCredentialManager | None = None


def get_credential_manager() -> SplunkCredentialManager:
    """Get or create global SplunkCredentialManager instance."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = SplunkCredentialManager()
    return _credential_manager
