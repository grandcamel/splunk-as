"""Data input commands for Splunk Assistant Skills CLI."""

from __future__ import annotations

from typing import Any

import click

from splunk_as import (
    format_json,
    format_table,
    print_success,
    print_warning,
    validate_path_component,
)

from ..cli_utils import build_endpoint, get_client_from_context, handle_cli_errors


@click.group()
def input() -> None:
    """Data input management.

    Manage HTTP inputs, scripted inputs, and monitors.
    """
    pass


# ============================================================================
# HTTP Event Collector (HEC) Commands
# ============================================================================


@input.group()
def hec() -> None:
    """HTTP Event Collector management.

    Manage HEC tokens and inputs.
    """
    pass


@hec.command(name="list")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_hec(ctx: click.Context, output: str) -> None:
    """List HEC tokens.

    Example:
        splunk-as input hec list
    """
    client = get_client_from_context(ctx)
    response = client.get(
        "/servicesNS/-/-/data/inputs/http",
        operation="list HEC tokens",
    )

    tokens = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        tokens.append(
            {
                "name": entry.get("name"),
                "disabled": content.get("disabled", False),
                "index": content.get("index", ""),
                "sourcetype": content.get("sourcetype", ""),
            }
        )

    if output == "json":
        click.echo(format_json(tokens))
    else:
        if not tokens:
            click.echo("No HEC tokens found.")
            return
        click.echo(format_table(tokens))
        print_success(f"Found {len(tokens)} HEC tokens")


@hec.command()
@click.argument("name")
@click.option("--index", "-i", help="Default index.")
@click.option("--sourcetype", "-s", help="Default sourcetype.")
@click.option("--source", help="Default source.")
@click.option("--disabled/--enabled", default=False, help="Create disabled.")
@click.pass_context
@handle_cli_errors
def create(
    ctx: click.Context,
    name: str,
    index: str | None,
    sourcetype: str | None,
    source: str | None,
    disabled: bool,
) -> None:
    """Create a new HEC token.

    Example:
        splunk-as input hec create my_token --index main --sourcetype json
    """
    client = get_client_from_context(ctx)

    data: dict[str, Any] = {"name": name}
    if index:
        data["index"] = index
    if sourcetype:
        data["sourcetype"] = sourcetype
    if source:
        data["source"] = source
    if disabled:
        data["disabled"] = "1"

    response = client.post(
        "/servicesNS/nobody/splunk_httpinput/data/inputs/http",
        data=data,
        operation="create HEC token",
    )

    # Extract token from response
    if "entry" in response and response["entry"]:
        content = response["entry"][0].get("content", {})
        token = content.get("token", "")
        print_success(f"Created HEC token: {name}")
        if token:
            click.echo(f"Token: {token}")
    else:
        print_success(f"Created HEC token: {name}")


@hec.command()
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation.")
@click.pass_context
@handle_cli_errors
def delete(ctx: click.Context, name: str, force: bool) -> None:
    """Delete an HEC token.

    Example:
        splunk-as input hec delete my_token
    """
    safe_name = validate_path_component(name, "name")

    if not force:
        print_warning(f"This will delete HEC token: {name}")
        if not click.confirm("Are you sure?"):
            click.echo("Cancelled.")
            return

    client = get_client_from_context(ctx)
    client.delete(
        f"/servicesNS/-/-/data/inputs/http/{safe_name}",
        operation="delete HEC token",
    )
    print_success(f"Deleted HEC token: {name}")


# ============================================================================
# Monitor Commands
# ============================================================================


@input.group()
def monitor() -> None:
    """File and directory monitor management.

    Manage file and directory monitoring inputs.
    """
    pass


@monitor.command(name="list")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_monitors(ctx: click.Context, output: str) -> None:
    """List file monitors.

    Example:
        splunk-as input monitor list
    """
    client = get_client_from_context(ctx)
    response = client.get(
        "/servicesNS/-/-/data/inputs/monitor",
        operation="list monitors",
    )

    monitors = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        monitors.append(
            {
                "name": entry.get("name"),
                "disabled": content.get("disabled", False),
                "index": content.get("index", ""),
                "sourcetype": content.get("sourcetype", ""),
            }
        )

    if output == "json":
        click.echo(format_json(monitors))
    else:
        if not monitors:
            click.echo("No monitors found.")
            return
        click.echo(format_table(monitors))
        print_success(f"Found {len(monitors)} monitors")


# ============================================================================
# Scripted Input Commands
# ============================================================================


@input.group()
def script() -> None:
    """Scripted input management.

    Manage scripted data inputs.
    """
    pass


@script.command(name="list")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_scripts(ctx: click.Context, output: str) -> None:
    """List scripted inputs.

    Example:
        splunk-as input script list
    """
    client = get_client_from_context(ctx)
    response = client.get(
        "/servicesNS/-/-/data/inputs/script",
        operation="list scripted inputs",
    )

    scripts = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        scripts.append(
            {
                "name": entry.get("name"),
                "disabled": content.get("disabled", False),
                "interval": content.get("interval", ""),
                "index": content.get("index", ""),
            }
        )

    if output == "json":
        click.echo(format_json(scripts))
    else:
        if not scripts:
            click.echo("No scripted inputs found.")
            return
        click.echo(format_table(scripts))
        print_success(f"Found {len(scripts)} scripted inputs")


# ============================================================================
# Summary Command
# ============================================================================


@input.command()
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def summary(ctx: click.Context, output: str) -> None:
    """Show summary of all data inputs.

    Example:
        splunk-as input summary
    """
    client = get_client_from_context(ctx)

    stats = {
        "hec_tokens": 0,
        "monitors": 0,
        "scripts": 0,
    }

    # Count HEC tokens
    try:
        response = client.get("/servicesNS/-/-/data/inputs/http", operation="count HEC")
        stats["hec_tokens"] = len(response.get("entry", []))
    except Exception:
        pass

    # Count monitors
    try:
        response = client.get(
            "/servicesNS/-/-/data/inputs/monitor", operation="count monitors"
        )
        stats["monitors"] = len(response.get("entry", []))
    except Exception:
        pass

    # Count scripts
    try:
        response = client.get(
            "/servicesNS/-/-/data/inputs/script", operation="count scripts"
        )
        stats["scripts"] = len(response.get("entry", []))
    except Exception:
        pass

    if output == "json":
        click.echo(format_json(stats))
    else:
        click.echo("Data Input Summary:")
        click.echo(f"  HEC Tokens: {stats['hec_tokens']}")
        click.echo(f"  File Monitors: {stats['monitors']}")
        click.echo(f"  Scripted Inputs: {stats['scripts']}")
