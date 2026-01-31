"""Configuration and shell completion commands for Splunk Assistant Skills CLI."""

from __future__ import annotations

import os
import sys
from typing import Any

import click

from splunk_as import format_json, get_config, print_error, print_success, print_warning


@click.group()
def config() -> None:
    """Configuration management.

    View, validate, and manage CLI configuration.
    """
    pass


@config.command()
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def show(output: str) -> None:
    """Show current configuration.

    Displays the active configuration from all sources
    (environment variables, config files, defaults).

    Example:
        splunk-as config show
    """
    cfg = get_config()

    # Redact sensitive values
    safe_config: dict[str, Any] = {}
    sensitive_keys = {"token", "password", "secret", "key", "credential"}

    for key, value in cfg.items():
        if any(s in key.lower() for s in sensitive_keys) and value:
            safe_config[key] = "[REDACTED]"
        else:
            safe_config[key] = value

    if output == "json":
        click.echo(format_json(safe_config))
    else:
        click.echo("Current Configuration:")
        click.echo("-" * 40)
        for key, value in sorted(safe_config.items()):
            click.echo(f"  {key}: {value}")


@config.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed validation results.")
def validate(verbose: bool) -> None:
    """Validate current configuration.

    Checks that all required settings are present and valid.

    Example:
        splunk-as config validate
        splunk-as config validate --verbose
    """
    cfg = get_config()
    errors: list[str] = []
    warnings: list[str] = []

    # Check required URL
    url = cfg.get("url") or cfg.get("site_url")
    if not url:
        errors.append("Missing Splunk URL (SPLUNK_SITE_URL or config file 'url')")
    elif not url.startswith(("http://", "https://")):
        errors.append(
            f"Invalid URL format: {url} (must start with http:// or https://)"
        )

    # Check authentication
    token = cfg.get("token")
    username = cfg.get("username")
    password = cfg.get("password")

    if not token and not (username and password):
        errors.append(
            "Missing authentication: set SPLUNK_TOKEN or both SPLUNK_USERNAME/SPLUNK_PASSWORD"
        )
    elif token and (username or password):
        warnings.append(
            "Both token and username/password configured; token will be used"
        )

    # Check port
    port = cfg.get("port") or cfg.get("management_port")
    if port:
        try:
            port_int = int(port)
            if not (1 <= port_int <= 65535):
                errors.append(f"Invalid port: {port} (must be 1-65535)")
        except (ValueError, TypeError):
            errors.append(f"Invalid port format: {port}")

    # Check SSL setting
    verify_ssl = cfg.get("verify_ssl")
    if verify_ssl is False:
        warnings.append("SSL verification is disabled (not recommended for production)")

    # Output results
    if verbose:
        click.echo("Configuration Sources:")
        click.echo("-" * 40)

        # Check environment variables
        env_vars = [
            "SPLUNK_SITE_URL",
            "SPLUNK_TOKEN",
            "SPLUNK_USERNAME",
            "SPLUNK_PASSWORD",
            "SPLUNK_MANAGEMENT_PORT",
            "SPLUNK_VERIFY_SSL",
            "SPLUNK_DEFAULT_APP",
            "SPLUNK_DEFAULT_INDEX",
        ]
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                # Redact sensitive values
                if any(s in var.lower() for s in ["token", "password"]):
                    click.echo(f"  {var}: [SET]")
                else:
                    click.echo(f"  {var}: {value}")
            else:
                click.echo(f"  {var}: (not set)")

        click.echo()

    # Print warnings
    for warning in warnings:
        print_warning(warning)

    # Print errors or success
    if errors:
        for error in errors:
            print_error(error)
        click.echo()
        click.echo("Configuration is INVALID")
        sys.exit(1)
    else:
        print_success("Configuration is valid")


@config.command()
def sources() -> None:
    """Show configuration file locations.

    Lists all configuration file locations and which ones exist.

    Example:
        splunk-as config sources
    """
    click.echo("Configuration Sources (highest priority first):")
    click.echo("-" * 50)

    sources_list = [
        ("Environment Variables", "SPLUNK_* environment variables"),
        (".claude/settings.local.json", "Personal settings (gitignored)"),
        (".claude/settings.json", "Team/project settings"),
        ("Built-in defaults", "Library defaults"),
    ]

    for i, (source, description) in enumerate(sources_list, 1):
        if source.endswith(".json"):
            exists = os.path.exists(source)
            status = "✓ exists" if exists else "✗ not found"
            click.echo(f"  {i}. {source} - {status}")
        else:
            click.echo(f"  {i}. {source}")
        click.echo(f"     {description}")
        click.echo()


# ============================================================================
# Shell Completion Commands
# ============================================================================


@click.group()
def completion() -> None:
    """Shell completion support.

    Generate shell completion scripts for bash, zsh, or fish.
    """
    pass


@completion.command()
def bash() -> None:
    """Generate bash completion script.

    To enable completion, add to your ~/.bashrc:
        eval "$(_SPLUNK_AS_COMPLETE=bash_source splunk-as)"

    Or save to a file and source it:
        splunk-as completion bash > ~/.splunk-as-complete.bash
        source ~/.splunk-as-complete.bash

    Example:
        splunk-as completion bash >> ~/.bashrc
    """
    # Click's built-in completion
    click.echo('eval "$(_SPLUNK_AS_COMPLETE=bash_source splunk-as)"')


@completion.command()
def zsh() -> None:
    """Generate zsh completion script.

    To enable completion, add to your ~/.zshrc:
        eval "$(_SPLUNK_AS_COMPLETE=zsh_source splunk-as)"

    Or save to a file and source it:
        splunk-as completion zsh > ~/.splunk-as-complete.zsh
        source ~/.splunk-as-complete.zsh

    Example:
        splunk-as completion zsh >> ~/.zshrc
    """
    # Click's built-in completion
    click.echo('eval "$(_SPLUNK_AS_COMPLETE=zsh_source splunk-as)"')


@completion.command()
def fish() -> None:
    """Generate fish completion script.

    To enable completion, save to fish completions directory:
        splunk-as completion fish > ~/.config/fish/completions/splunk-as.fish

    Example:
        splunk-as completion fish > ~/.config/fish/completions/splunk-as.fish
    """
    # Click's built-in completion
    click.echo("_SPLUNK_AS_COMPLETE=fish_source splunk-as | source")


@completion.command()
@click.option(
    "--shell",
    "-s",
    type=click.Choice(["bash", "zsh", "fish"]),
    help="Shell type (auto-detected if not specified).",
)
def install(shell: str | None) -> None:
    """Install shell completion (interactive).

    Automatically detects your shell and provides installation instructions.

    Example:
        splunk-as completion install
        splunk-as completion install --shell zsh
    """
    if not shell:
        # Auto-detect shell
        shell_env = os.environ.get("SHELL", "")
        if "zsh" in shell_env:
            shell = "zsh"
        elif "fish" in shell_env:
            shell = "fish"
        else:
            shell = "bash"

    click.echo(f"Detected shell: {shell}")
    click.echo()

    if shell == "bash":
        click.echo("To enable bash completion, add this line to ~/.bashrc:")
        click.echo()
        click.echo('  eval "$(_SPLUNK_AS_COMPLETE=bash_source splunk-as)"')
        click.echo()
        click.echo("Then reload your shell:")
        click.echo("  source ~/.bashrc")
    elif shell == "zsh":
        click.echo("To enable zsh completion, add this line to ~/.zshrc:")
        click.echo()
        click.echo('  eval "$(_SPLUNK_AS_COMPLETE=zsh_source splunk-as)"')
        click.echo()
        click.echo("Then reload your shell:")
        click.echo("  source ~/.zshrc")
    elif shell == "fish":
        click.echo("To enable fish completion, run:")
        click.echo()
        click.echo(
            "  splunk-as completion fish > ~/.config/fish/completions/splunk-as.fish"
        )
        click.echo()
        click.echo("Completion will be active in new fish sessions.")

    click.echo()
    print_success(f"Follow the instructions above to enable {shell} completion")
