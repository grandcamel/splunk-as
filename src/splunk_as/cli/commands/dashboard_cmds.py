"""Dashboard commands for Splunk Assistant Skills CLI."""

from __future__ import annotations

import click

from splunk_as import (
    format_json,
    format_table,
    print_success,
    print_warning,
    validate_file_path,
    validate_path_component,
)

from ..cli_utils import build_endpoint, get_client_from_context, handle_cli_errors


@click.group()
def dashboard() -> None:
    """Dashboard management.

    List, export, and manage Splunk dashboards.
    """
    pass


@dashboard.command(name="list")
@click.option("--app", "-a", help="Filter by app.")
@click.option("--owner", help="Filter by owner.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_dashboards(
    ctx: click.Context, app: str | None, owner: str | None, output: str
) -> None:
    """List all dashboards.

    Example:
        splunk-as dashboard list --app search
    """
    client = get_client_from_context(ctx)
    endpoint = build_endpoint("/data/ui/views", app=app, owner=owner)
    response = client.get(endpoint, operation="list dashboards")

    dashboards = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        dashboards.append(
            {
                "name": entry.get("name"),
                "app": entry.get("acl", {}).get("app", ""),
                "label": content.get("label", ""),
                "isDashboard": content.get("isDashboard", False),
            }
        )

    if output == "json":
        click.echo(format_json(dashboards))
    else:
        if not dashboards:
            click.echo("No dashboards found.")
            return
        click.echo(format_table(dashboards))
        print_success(f"Found {len(dashboards)} dashboards")


@dashboard.command()
@click.argument("name")
@click.option("--app", "-a", default="search", help="App context.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json", "xml"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def get(ctx: click.Context, name: str, app: str, output: str) -> None:
    """Get dashboard details.

    Example:
        splunk-as dashboard get my_dashboard --app search
    """
    safe_app = validate_path_component(app, "app")
    safe_name = validate_path_component(name, "name")

    client = get_client_from_context(ctx)
    response = client.get(
        f"/servicesNS/-/{safe_app}/data/ui/views/{safe_name}",
        operation="get dashboard",
    )

    if "entry" in response and response["entry"]:
        entry = response["entry"][0]
        content = entry.get("content", {})

        if output == "json":
            click.echo(format_json(entry))
        elif output == "xml":
            # Return the raw XML definition
            click.echo(content.get("eai:data", ""))
        else:
            click.echo(f"Name: {entry.get('name')}")
            click.echo(f"Label: {content.get('label', '')}")
            click.echo(f"App: {entry.get('acl', {}).get('app', '')}")
            click.echo(f"Owner: {entry.get('acl', {}).get('owner', '')}")
            click.echo(f"Is Dashboard: {content.get('isDashboard', False)}")


@dashboard.command()
@click.argument("name")
@click.option("--app", "-a", default="search", help="App context.")
@click.option("--output-file", "-o", help="Output file path (default: {name}.xml).")
@click.pass_context
@handle_cli_errors
def export(ctx: click.Context, name: str, app: str, output_file: str | None) -> None:
    """Export dashboard to XML file.

    Example:
        splunk-as dashboard export my_dashboard -o my_dashboard.xml
    """
    safe_app = validate_path_component(app, "app")
    safe_name = validate_path_component(name, "name")

    output_file = output_file or f"{name}.xml"
    validate_file_path(output_file, "output_file")

    client = get_client_from_context(ctx)
    response = client.get(
        f"/servicesNS/-/{safe_app}/data/ui/views/{safe_name}",
        operation="export dashboard",
    )

    if "entry" in response and response["entry"]:
        content = response["entry"][0].get("content", {})
        xml_data = content.get("eai:data", "")

        with open(output_file, "w") as f:
            f.write(xml_data)

        print_success(f"Exported dashboard to {output_file}")
    else:
        click.echo(f"Dashboard not found: {name}")


@dashboard.command(name="import")
@click.argument("file_path")
@click.option("--app", "-a", default="search", help="App context.")
@click.option("--name", "-n", help="Dashboard name (defaults to filename).")
@click.pass_context
@handle_cli_errors
def import_dashboard(
    ctx: click.Context, file_path: str, app: str, name: str | None
) -> None:
    """Import dashboard from XML file.

    Example:
        splunk-as dashboard import my_dashboard.xml --app search
    """
    import os

    validate_file_path(file_path, "file_path")
    safe_app = validate_path_component(app, "app")

    dashboard_name = name or os.path.splitext(os.path.basename(file_path))[0]

    with open(file_path, "r") as f:
        xml_content = f.read()

    client = get_client_from_context(ctx)
    client.post(
        f"/servicesNS/nobody/{safe_app}/data/ui/views",
        data={
            "name": dashboard_name,
            "eai:data": xml_content,
        },
        operation="import dashboard",
    )
    print_success(f"Imported dashboard: {dashboard_name}")


@dashboard.command()
@click.argument("name")
@click.option("--app", "-a", default="search", help="App context.")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation.")
@click.pass_context
@handle_cli_errors
def delete(ctx: click.Context, name: str, app: str, force: bool) -> None:
    """Delete a dashboard.

    Example:
        splunk-as dashboard delete my_dashboard --app search
    """
    safe_app = validate_path_component(app, "app")
    safe_name = validate_path_component(name, "name")

    if not force:
        print_warning(f"This will delete dashboard: {name}")
        if not click.confirm("Are you sure?"):
            click.echo("Cancelled.")
            return

    client = get_client_from_context(ctx)
    client.delete(
        f"/servicesNS/-/{safe_app}/data/ui/views/{safe_name}",
        operation="delete dashboard",
    )
    print_success(f"Deleted dashboard: {name}")
