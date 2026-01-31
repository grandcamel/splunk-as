"""User and role management commands for Splunk Assistant Skills CLI."""

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

from ..cli_utils import get_client_from_context, handle_cli_errors, output_results


@click.group()
def user() -> None:
    """User and role management.

    Manage Splunk users, roles, and capabilities.
    """
    pass


# ============================================================================
# User Commands
# ============================================================================


@user.command(name="list")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_users(ctx: click.Context, output: str) -> None:
    """List all users.

    Example:
        splunk-as user list
    """
    client = get_client_from_context(ctx)
    response = client.get("/authentication/users", operation="list users")

    users = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        roles = content.get("roles", [])
        users.append(
            {
                "name": entry.get("name"),
                "realname": content.get("realname", ""),
                "email": content.get("email", ""),
                "roles": ", ".join(roles) if isinstance(roles, list) else roles,
            }
        )

    output_results(users, output, success_msg=f"Found {len(users)} users")


@user.command()
@click.argument("username")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def get(ctx: click.Context, username: str, output: str) -> None:
    """Get user details.

    Example:
        splunk-as user get admin
    """
    safe_username = validate_path_component(username, "username")

    client = get_client_from_context(ctx)
    response = client.get(
        f"/authentication/users/{safe_username}",
        operation="get user",
    )

    if "entry" in response and response["entry"]:
        entry = response["entry"][0]
        content = entry.get("content", {})

        if output == "json":
            click.echo(format_json(entry))
        else:
            click.echo(f"Username: {entry.get('name')}")
            click.echo(f"Real Name: {content.get('realname', '')}")
            click.echo(f"Email: {content.get('email', '')}")
            roles = content.get("roles", [])
            click.echo(
                f"Roles: {', '.join(roles) if isinstance(roles, list) else roles}"
            )
            click.echo(f"Default App: {content.get('defaultApp', '')}")
            click.echo(f"Type: {content.get('type', '')}")


@user.command()
@click.argument("username")
@click.option("--password", "-p", required=True, help="User password.")
@click.option("--realname", help="Real name.")
@click.option("--email", help="Email address.")
@click.option("--roles", "-r", multiple=True, help="Roles to assign (can repeat).")
@click.option("--default-app", help="Default app.")
@click.pass_context
@handle_cli_errors
def create(
    ctx: click.Context,
    username: str,
    password: str,
    realname: str | None,
    email: str | None,
    roles: tuple[str, ...],
    default_app: str | None,
) -> None:
    """Create a new user.

    Example:
        splunk-as user create newuser -p password123 -r user
    """
    client = get_client_from_context(ctx)

    data: dict[str, Any] = {
        "name": username,
        "password": password,
    }
    if realname:
        data["realname"] = realname
    if email:
        data["email"] = email
    if roles:
        data["roles"] = list(roles)
    if default_app:
        data["defaultApp"] = default_app

    client.post(
        "/authentication/users",
        data=data,
        operation="create user",
    )
    print_success(f"Created user: {username}")


@user.command()
@click.argument("username")
@click.option("--password", "-p", help="New password.")
@click.option("--realname", help="Real name.")
@click.option("--email", help="Email address.")
@click.option(
    "--roles", "-r", multiple=True, help="Roles to assign (replaces existing)."
)
@click.option("--default-app", help="Default app.")
@click.pass_context
@handle_cli_errors
def update(
    ctx: click.Context,
    username: str,
    password: str | None,
    realname: str | None,
    email: str | None,
    roles: tuple[str, ...],
    default_app: str | None,
) -> None:
    """Update a user.

    Example:
        splunk-as user update admin --email admin@example.com
    """
    safe_username = validate_path_component(username, "username")

    data: dict[str, Any] = {}
    if password:
        data["password"] = password
    if realname:
        data["realname"] = realname
    if email:
        data["email"] = email
    if roles:
        data["roles"] = list(roles)
    if default_app:
        data["defaultApp"] = default_app

    if not data:
        click.echo("No updates specified.")
        return

    client = get_client_from_context(ctx)
    client.post(
        f"/authentication/users/{safe_username}",
        data=data,
        operation="update user",
    )
    print_success(f"Updated user: {username}")


@user.command()
@click.argument("username")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation.")
@click.pass_context
@handle_cli_errors
def delete(ctx: click.Context, username: str, force: bool) -> None:
    """Delete a user.

    Example:
        splunk-as user delete olduser
    """
    safe_username = validate_path_component(username, "username")

    if not force:
        print_warning(f"This will delete user: {username}")
        if not click.confirm("Are you sure?"):
            click.echo("Cancelled.")
            return

    client = get_client_from_context(ctx)
    client.delete(
        f"/authentication/users/{safe_username}",
        operation="delete user",
    )
    print_success(f"Deleted user: {username}")


# ============================================================================
# Role Commands
# ============================================================================


@user.group()
def role() -> None:
    """Role management.

    Manage Splunk roles and their capabilities.
    """
    pass


@role.command(name="list")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_roles(ctx: click.Context, output: str) -> None:
    """List all roles.

    Example:
        splunk-as user role list
    """
    client = get_client_from_context(ctx)
    response = client.get("/authorization/roles", operation="list roles")

    roles = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        roles.append(
            {
                "name": entry.get("name"),
                "imported_roles": ", ".join(content.get("imported_roles", [])),
                "default_app": content.get("defaultApp", ""),
            }
        )

    output_results(roles, output, success_msg=f"Found {len(roles)} roles")


@role.command(name="get")
@click.argument("rolename")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def get_role(ctx: click.Context, rolename: str, output: str) -> None:
    """Get role details.

    Example:
        splunk-as user role get admin
    """
    safe_rolename = validate_path_component(rolename, "rolename")

    client = get_client_from_context(ctx)
    response = client.get(
        f"/authorization/roles/{safe_rolename}",
        operation="get role",
    )

    if "entry" in response and response["entry"]:
        entry = response["entry"][0]
        content = entry.get("content", {})

        if output == "json":
            click.echo(format_json(entry))
        else:
            click.echo(f"Role: {entry.get('name')}")
            click.echo(f"Default App: {content.get('defaultApp', '')}")
            imported = content.get("imported_roles", [])
            click.echo(f"Imported Roles: {', '.join(imported)}")
            caps = content.get("capabilities", [])
            click.echo(f"Capabilities ({len(caps)}):")
            for cap in caps[:20]:
                click.echo(f"  - {cap}")
            if len(caps) > 20:
                click.echo(f"  ... and {len(caps) - 20} more")


@role.command(name="create")
@click.argument("rolename")
@click.option("--imported-roles", "-i", multiple=True, help="Roles to inherit from.")
@click.option("--capabilities", "-c", multiple=True, help="Capabilities to grant.")
@click.option("--default-app", help="Default app.")
@click.pass_context
@handle_cli_errors
def create_role(
    ctx: click.Context,
    rolename: str,
    imported_roles: tuple[str, ...],
    capabilities: tuple[str, ...],
    default_app: str | None,
) -> None:
    """Create a new role.

    Example:
        splunk-as user role create myrole -i user -c search
    """
    client = get_client_from_context(ctx)

    data: dict[str, Any] = {"name": rolename}
    if imported_roles:
        data["imported_roles"] = list(imported_roles)
    if capabilities:
        data["capabilities"] = list(capabilities)
    if default_app:
        data["defaultApp"] = default_app

    client.post(
        "/authorization/roles",
        data=data,
        operation="create role",
    )
    print_success(f"Created role: {rolename}")


@role.command(name="delete")
@click.argument("rolename")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation.")
@click.pass_context
@handle_cli_errors
def delete_role(ctx: click.Context, rolename: str, force: bool) -> None:
    """Delete a role.

    Example:
        splunk-as user role delete myrole
    """
    safe_rolename = validate_path_component(rolename, "rolename")

    if not force:
        print_warning(f"This will delete role: {rolename}")
        if not click.confirm("Are you sure?"):
            click.echo("Cancelled.")
            return

    client = get_client_from_context(ctx)
    client.delete(
        f"/authorization/roles/{safe_rolename}",
        operation="delete role",
    )
    print_success(f"Deleted role: {rolename}")
