"""Metadata commands for Splunk Assistant Skills CLI."""

from __future__ import annotations

import click

from splunk_assistant_skills_lib import (
    format_json,
    format_table,
    get_splunk_client,
    print_success,
)

from ..cli_utils import handle_cli_errors


@click.group()
def metadata():
    """Index, source, and sourcetype discovery.

    Explore and discover metadata about your Splunk environment.
    """
    pass


@metadata.command()
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--filter", "-f", "filter_pattern", help="Filter indexes by name pattern.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def indexes(ctx, profile, filter_pattern, output):
    """List all indexes.

    Example:
        splunk-as metadata indexes
    """
    client = get_splunk_client(profile=profile)
    response = client.get("/data/indexes", operation="list indexes")

    indexes_list = []
    for entry in response.get("entry", []):
        name = entry.get("name")
        if filter_pattern and filter_pattern.lower() not in name.lower():
            continue
        content = entry.get("content", {})
        indexes_list.append(
            {
                "name": name,
                "totalEventCount": content.get("totalEventCount", 0),
                "currentDBSizeMB": content.get("currentDBSizeMB", 0),
                "maxDataSizeMB": content.get("maxDataSizeMB", 0),
                "disabled": content.get("disabled", False),
            }
        )

    if output == "json":
        click.echo(format_json(indexes_list))
    else:
        display_data = []
        for idx in indexes_list:
            display_data.append(
                {
                    "Index": idx["name"],
                    "Events": f"{idx['totalEventCount']:,}",
                    "Size (MB)": f"{idx['currentDBSizeMB']:.0f}",
                    "Disabled": "Yes" if idx["disabled"] else "No",
                }
            )
        click.echo(format_table(display_data))
        print_success(f"Found {len(indexes_list)} indexes")


@metadata.command("index-info")
@click.argument("index_name")
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
def index_info(ctx, index_name, profile, output):
    """Get detailed information about an index.

    Example:
        splunk-as metadata index-info main
    """
    client = get_splunk_client(profile=profile)
    response = client.get(f"/data/indexes/{index_name}", operation="get index info")

    if "entry" in response and response["entry"]:
        entry = response["entry"][0]
        content = entry.get("content", {})

        if output == "json":
            click.echo(format_json(content))
        else:
            click.echo(f"Index: {index_name}")
            click.echo(f"Total Events: {content.get('totalEventCount', 0):,}")
            click.echo(f"Current Size: {content.get('currentDBSizeMB', 0):.2f} MB")
            click.echo(f"Max Size: {content.get('maxDataSizeMB', 0)} MB")
            click.echo(f"Disabled: {content.get('disabled', False)}")
            click.echo(f"Data Type: {content.get('datatype', 'event')}")


@metadata.command()
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--index", "-i", help="Filter by index.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def sourcetypes(ctx, profile, index, output):
    """List all sourcetypes.

    Example:
        splunk-as metadata sourcetypes --index main
    """
    client = get_splunk_client(profile=profile)

    # Use metadata search to get sourcetypes
    search = "| metadata type=sourcetypes"
    if index:
        search += f" index={index}"
    search += " | table sourcetype, totalCount, recentTime | sort -totalCount"

    response = client.post(
        "/search/jobs/oneshot",
        data={"search": search, "output_mode": "json", "count": 1000},
        operation="list sourcetypes",
    )

    results = response.get("results", [])

    if output == "json":
        click.echo(format_json(results))
    else:
        if not results:
            click.echo("No sourcetypes found.")
            return

        display_data = []
        for r in results:
            display_data.append(
                {
                    "Sourcetype": r.get("sourcetype", ""),
                    "Count": f"{int(r.get('totalCount', 0)):,}",
                }
            )
        click.echo(format_table(display_data))
        print_success(f"Found {len(results)} sourcetypes")


@metadata.command()
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--index", "-i", help="Filter by index.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def sources(ctx, profile, index, output):
    """List all sources.

    Example:
        splunk-as metadata sources --index main
    """
    client = get_splunk_client(profile=profile)

    search = "| metadata type=sources"
    if index:
        search += f" index={index}"
    search += " | table source, totalCount | sort -totalCount | head 100"

    response = client.post(
        "/search/jobs/oneshot",
        data={"search": search, "output_mode": "json", "count": 1000},
        operation="list sources",
    )

    results = response.get("results", [])

    if output == "json":
        click.echo(format_json(results))
    else:
        if not results:
            click.echo("No sources found.")
            return

        display_data = []
        for r in results:
            display_data.append(
                {
                    "Source": r.get("source", "")[:60],
                    "Count": f"{int(r.get('totalCount', 0)):,}",
                }
            )
        click.echo(format_table(display_data))
        print_success(f"Found {len(results)} sources")


@metadata.command()
@click.argument("index_name")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--sourcetype", "-s", help="Filter by sourcetype.")
@click.option("--earliest", "-e", default="-24h", help="Earliest time.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def fields(ctx, index_name, profile, sourcetype, earliest, output):
    """Get field summary for an index.

    Example:
        splunk-as metadata fields main --sourcetype access_combined
    """
    client = get_splunk_client(profile=profile)

    search = f"index={index_name}"
    if sourcetype:
        search += f" sourcetype={sourcetype}"
    search += " | fieldsummary | sort -count | head 50"

    response = client.post(
        "/search/jobs/oneshot",
        data={
            "search": search,
            "earliest_time": earliest,
            "output_mode": "json",
            "count": 100,
        },
        operation="get field summary",
    )

    results = response.get("results", [])

    if output == "json":
        click.echo(format_json(results))
    else:
        if not results:
            click.echo("No fields found.")
            return

        display_data = []
        for r in results:
            display_data.append(
                {
                    "Field": r.get("field", ""),
                    "Count": f"{int(r.get('count', 0)):,}",
                    "Distinct": r.get("distinct_count", ""),
                }
            )
        click.echo(format_table(display_data))
        print_success(f"Found {len(results)} fields")


@metadata.command()
@click.argument("metadata_type", type=click.Choice(["hosts", "sources", "sourcetypes"]))
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--index", "-i", help="Filter by index.")
@click.option("--earliest", "-e", default="-24h", help="Earliest time.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def search(ctx, metadata_type, profile, index, earliest, output):
    """Search metadata using the metadata command.

    Example:
        splunk-as metadata search sourcetypes --index main
    """
    client = get_splunk_client(profile=profile)

    search_spl = f"| metadata type={metadata_type}"
    if index:
        search_spl += f" index={index}"
    search_spl += " | table * | sort -totalCount | head 100"

    response = client.post(
        "/search/jobs/oneshot",
        data={
            "search": search_spl,
            "earliest_time": earliest,
            "output_mode": "json",
            "count": 1000,
        },
        operation=f"metadata search {metadata_type}",
    )

    results = response.get("results", [])

    if output == "json":
        click.echo(format_json(results))
    else:
        if not results:
            click.echo(f"No {metadata_type} found.")
            return

        click.echo(format_table(results[:50]))
        print_success(f"Found {len(results)} {metadata_type}")
