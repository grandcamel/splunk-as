"""Admin commands for Splunk Assistant Skills CLI."""

from __future__ import annotations

import json

import click

from splunk_assistant_skills_lib import (
    format_json,
    format_table,
    get_splunk_client,
    print_success,
)

from ..cli_utils import handle_cli_errors, parse_json_arg


@click.group()
def admin():
    """Server administration and REST API access.

    Check server status, health, and make generic REST calls.
    """
    pass


@admin.command()
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def info(ctx, profile, output):
    """Get server information.

    Example:
        splunk-as admin info
    """
    client = get_splunk_client(profile=profile)
    response = client.get("/server/info", operation="get server info")

    if "entry" in response and response["entry"]:
        content = response["entry"][0].get("content", {})

        if output == "json":
            click.echo(format_json(content))
        else:
            click.echo(f"Server: {content.get('serverName', 'Unknown')}")
            click.echo(f"Version: {content.get('version', 'Unknown')}")
            click.echo(f"Build: {content.get('build', 'Unknown')}")
            click.echo(f"OS: {content.get('os_name', 'Unknown')}")
            click.echo(f"CPU Arch: {content.get('cpu_arch', 'Unknown')}")
            click.echo(f"License: {content.get('licenseState', 'Unknown')}")


@admin.command()
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def status(ctx, profile, output):
    """Get server status.

    Example:
        splunk-as admin status
    """
    client = get_splunk_client(profile=profile)
    response = client.get("/server/status", operation="get server status")

    if "entry" in response and response["entry"]:
        content = response["entry"][0].get("content", {})

        if output == "json":
            click.echo(format_json(content))
        else:
            click.echo(f"Status: {content.get('status', 'Unknown')}")


@admin.command()
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def health(ctx, profile, output):
    """Get server health status.

    Example:
        splunk-as admin health
    """
    client = get_splunk_client(profile=profile)
    response = client.get("/server/health/splunkd", operation="get health")

    if "entry" in response and response["entry"]:
        content = response["entry"][0].get("content", {})

        if output == "json":
            click.echo(format_json(content))
        else:
            health_status = content.get("health", "Unknown")
            click.echo(f"Health: {health_status}")
            if "features" in content:
                for feature, status in content["features"].items():
                    click.echo(f"  {feature}: {status.get('health', 'Unknown')}")


@admin.command(name="list-users")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_users(ctx, profile, output):
    """List all users.

    Example:
        splunk-as admin list-users
    """
    client = get_splunk_client(profile=profile)
    response = client.get("/authentication/users", operation="list users")

    users = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        users.append(
            {
                "name": entry.get("name"),
                "realname": content.get("realname", ""),
                "roles": ", ".join(content.get("roles", [])),
                "email": content.get("email", ""),
            }
        )

    if output == "json":
        click.echo(format_json(users))
    else:
        click.echo(format_table(users))
        print_success(f"Found {len(users)} users")


@admin.command(name="list-roles")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_roles(ctx, profile, output):
    """List all roles.

    Example:
        splunk-as admin list-roles
    """
    client = get_splunk_client(profile=profile)
    response = client.get("/authorization/roles", operation="list roles")

    roles = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        roles.append(
            {
                "name": entry.get("name"),
                "imported_roles": ", ".join(content.get("imported_roles", [])),
                "capabilities_count": len(content.get("capabilities", [])),
            }
        )

    if output == "json":
        click.echo(format_json(roles))
    else:
        click.echo(format_table(roles))
        print_success(f"Found {len(roles)} roles")


@admin.command("rest-get")
@click.argument("endpoint")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--app", "-a", help="App context.")
@click.option("--owner", help="Owner context.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="json",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def rest_get(ctx, endpoint, profile, app, owner, output):
    """Make a GET request to a REST endpoint.

    Example:
        splunk-as admin rest-get /services/server/info
    """
    client = get_splunk_client(profile=profile)

    # Build full endpoint if app/owner specified
    if app and owner:
        endpoint = f"/servicesNS/{owner}/{app}{endpoint}"
    elif app:
        endpoint = f"/servicesNS/-/{app}{endpoint}"

    response = client.get(endpoint, operation=f"GET {endpoint}")

    if output == "json":
        click.echo(format_json(response))
    else:
        click.echo(format_json(response))


@admin.command("rest-post")
@click.argument("endpoint")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--data", "-d", help="POST data (JSON or key=value pairs).")
@click.option("--app", "-a", help="App context.")
@click.option("--owner", help="Owner context.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="json",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def rest_post(ctx, endpoint, profile, data, app, owner, output):
    """Make a POST request to a REST endpoint.

    Example:
        splunk-as admin rest-post /services/saved/searches -d '{"name": "test"}'
    """
    client = get_splunk_client(profile=profile)

    # Build full endpoint if app/owner specified
    if app and owner:
        endpoint = f"/servicesNS/{owner}/{app}{endpoint}"
    elif app:
        endpoint = f"/servicesNS/-/{app}{endpoint}"

    # Parse data
    post_data = None
    if data:
        try:
            post_data = json.loads(data)
        except json.JSONDecodeError:
            # Try key=value format
            post_data = dict(item.split("=", 1) for item in data.split("&") if "=" in item)

    response = client.post(endpoint, data=post_data, operation=f"POST {endpoint}")

    if output == "json":
        click.echo(format_json(response))
    else:
        click.echo(format_json(response))
