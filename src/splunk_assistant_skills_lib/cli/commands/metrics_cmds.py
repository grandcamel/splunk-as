"""Metrics commands for Splunk Assistant Skills CLI."""

from __future__ import annotations

import click

from splunk_assistant_skills_lib import (
    format_json,
    format_search_results,
    format_table,
    get_search_defaults,
    get_splunk_client,
    print_success,
    validate_time_modifier,
)

from ..cli_utils import handle_cli_errors


@click.group()
def metrics():
    """Real-time metrics operations.

    Query and analyze Splunk metrics using mstats and mcatalog.
    """
    pass


@metrics.command(name="list")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--index", "-i", help="Filter by metrics index.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_metrics(ctx, profile, index, output):
    """List available metrics.

    Example:
        splunk-as metrics list --index my_metrics
    """
    client = get_splunk_client(profile=profile)

    # Use mcatalog to discover metrics
    spl = "| mcatalog values(metric_name) as metrics"
    if index:
        spl += f" WHERE index={index}"
    spl += " | mvexpand metrics | sort metrics"

    response = client.post(
        "/search/jobs/oneshot",
        data={"search": spl, "output_mode": "json", "count": 1000},
        operation="list metrics",
    )

    results = response.get("results", [])

    if output == "json":
        click.echo(format_json(results))
    else:
        if not results:
            click.echo("No metrics found.")
            return

        metrics_list = [r.get("metrics", "") for r in results if r.get("metrics")]
        for metric in metrics_list[:50]:
            click.echo(f"  - {metric}")
        print_success(f"Found {len(metrics_list)} metrics")


@metrics.command()
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
def indexes(ctx, profile, output):
    """List metrics indexes.

    Example:
        splunk-as metrics indexes
    """
    client = get_splunk_client(profile=profile)

    response = client.get(
        "/data/indexes",
        params={"datatype": "metric"},
        operation="list metrics indexes",
    )

    indexes_list = []
    for entry in response.get("entry", []):
        content = entry.get("content", {})
        if content.get("datatype") == "metric":
            indexes_list.append(
                {
                    "name": entry.get("name"),
                    "totalEventCount": content.get("totalEventCount", 0),
                    "currentDBSizeMB": content.get("currentDBSizeMB", 0),
                }
            )

    if output == "json":
        click.echo(format_json(indexes_list))
    else:
        if not indexes_list:
            click.echo("No metrics indexes found.")
            return
        click.echo(format_table(indexes_list))
        print_success(f"Found {len(indexes_list)} metrics indexes")


@metrics.command()
@click.argument("metric_name")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--index", "-i", help="Metrics index.")
@click.option("--earliest", "-e", default="-1h", help="Earliest time.")
@click.option("--latest", "-l", default="now", help="Latest time.")
@click.option("--span", default="1m", help="Time span for aggregation.")
@click.option(
    "--agg",
    type=click.Choice(["avg", "sum", "min", "max", "count"]),
    default="avg",
    help="Aggregation function.",
)
@click.option("--split-by", help="Field to split by.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def mstats(ctx, metric_name, profile, index, earliest, latest, span, agg, split_by, output):
    """Query metrics using mstats.

    Example:
        splunk-as metrics mstats cpu.percent --index my_metrics --span 5m
    """
    client = get_splunk_client(profile=profile)
    defaults = get_search_defaults(profile)

    earliest = validate_time_modifier(earliest)
    latest = validate_time_modifier(latest)

    # Build mstats query
    spl = f"| mstats {agg}({metric_name}) as value"

    where_clause = []
    if index:
        where_clause.append(f"index={index}")
    if where_clause:
        spl += f" WHERE {' AND '.join(where_clause)}"

    if split_by:
        spl += f" BY {split_by}"

    spl += f" span={span}"

    response = client.post(
        "/search/jobs/oneshot",
        data={
            "search": spl,
            "earliest_time": earliest,
            "latest_time": latest,
            "output_mode": "json",
            "count": 1000,
        },
        operation="mstats query",
    )

    results = response.get("results", [])

    if output == "json":
        click.echo(format_json(results))
    else:
        if not results:
            click.echo(f"No data found for metric: {metric_name}")
            return
        click.echo(format_search_results(results))
        print_success(f"Found {len(results)} data points")


@metrics.command()
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--index", "-i", help="Metrics index.")
@click.option("--metric", "-m", help="Filter by metric name pattern.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def mcatalog(ctx, profile, index, metric, output):
    """Explore metrics catalog.

    Example:
        splunk-as metrics mcatalog --index my_metrics --metric "cpu.*"
    """
    client = get_splunk_client(profile=profile)

    # Build mcatalog query
    spl = "| mcatalog values(metric_name) as metric_name, values(_dims) as dimensions"

    where_clause = []
    if index:
        where_clause.append(f"index={index}")
    if metric:
        where_clause.append(f'metric_name="{metric}"')
    if where_clause:
        spl += f" WHERE {' AND '.join(where_clause)}"

    spl += " | stats count by metric_name, dimensions"

    response = client.post(
        "/search/jobs/oneshot",
        data={"search": spl, "output_mode": "json", "count": 1000},
        operation="mcatalog query",
    )

    results = response.get("results", [])

    if output == "json":
        click.echo(format_json(results))
    else:
        if not results:
            click.echo("No metrics catalog entries found.")
            return
        click.echo(format_table(results[:50]))
        print_success(f"Found {len(results)} catalog entries")
