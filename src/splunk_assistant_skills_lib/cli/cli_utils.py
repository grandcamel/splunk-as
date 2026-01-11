"""CLI utility functions for Splunk Assistant Skills."""

from __future__ import annotations

import functools
import json
import sys
from typing import Any, Callable, TypeVar

import click

from splunk_assistant_skills_lib import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    SearchQuotaError,
    ServerError,
    SplunkError,
    ValidationError,
    print_error,
)

F = TypeVar("F", bound=Callable[..., Any])


def handle_cli_errors(func: F) -> F:
    """Decorator to handle exceptions in CLI commands.

    Catches SplunkError exceptions and prints user-friendly error messages,
    then exits with appropriate exit codes.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print_error(f"Validation error: {e}")
            sys.exit(1)
        except AuthenticationError as e:
            print_error(f"Authentication failed: {e}")
            sys.exit(2)
        except AuthorizationError as e:
            print_error(f"Authorization denied: {e}")
            sys.exit(3)
        except NotFoundError as e:
            print_error(f"Not found: {e}")
            sys.exit(4)
        except RateLimitError as e:
            print_error(f"Rate limit exceeded: {e}")
            sys.exit(5)
        except SearchQuotaError as e:
            print_error(f"Search quota exceeded: {e}")
            sys.exit(6)
        except ServerError as e:
            print_error(f"Server error: {e}")
            sys.exit(7)
        except SplunkError as e:
            print_error(f"Splunk error: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print_error("Interrupted by user")
            sys.exit(130)
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            sys.exit(1)

    return wrapper  # type: ignore[return-value]


def parse_comma_list(value: str | None) -> list[str] | None:
    """Parse a comma-separated string into a list.

    Args:
        value: Comma-separated string or None

    Returns:
        List of stripped strings, or None if input was None/empty
    """
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_json_arg(value: str | None) -> dict[str, Any] | None:
    """Parse a JSON string argument.

    Args:
        value: JSON string or None

    Returns:
        Parsed dict, or None if input was None/empty

    Raises:
        click.BadParameter: If JSON parsing fails
    """
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise click.BadParameter(f"Invalid JSON: {e}")


def validate_positive_int(
    ctx: click.Context, param: click.Parameter, value: int | None
) -> int | None:
    """Click callback to validate positive integers."""
    if value is not None and value <= 0:
        raise click.BadParameter("must be a positive integer")
    return value


def validate_non_negative_int(
    ctx: click.Context, param: click.Parameter, value: int | None
) -> int | None:
    """Click callback to validate non-negative integers."""
    if value is not None and value < 0:
        raise click.BadParameter("must be a non-negative integer")
    return value


# Common Click options that can be reused across commands
profile_option = click.option(
    "--profile",
    "-p",
    envvar="SPLUNK_PROFILE",
    help="Splunk profile to use for authentication.",
)

output_option = click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json", "csv"]),
    default="text",
    help="Output format.",
)

output_text_json_option = click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)

verbose_option = click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output.",
)

quiet_option = click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress non-essential output.",
)
