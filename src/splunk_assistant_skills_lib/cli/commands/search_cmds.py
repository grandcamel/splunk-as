"""Search commands for Splunk Assistant Skills CLI."""

from __future__ import annotations

import click

from splunk_assistant_skills_lib import (
    build_search,
    estimate_search_complexity,
    export_csv,
    format_json,
    format_search_results,
    get_api_settings,
    get_search_defaults,
    get_splunk_client,
    optimize_spl,
    parse_spl_commands,
    print_success,
    print_warning,
    validate_sid,
    validate_spl,
    validate_spl_syntax,
    validate_time_modifier,
    wait_for_job,
)

from ..cli_utils import handle_cli_errors, parse_comma_list


@click.group()
def search():
    """SPL query execution commands.

    Execute Splunk searches in various modes: oneshot, normal, or blocking.
    """
    pass


# -----------------------------------------------------------------------------
# Oneshot search
# -----------------------------------------------------------------------------


def _oneshot_impl(
    spl: str,
    profile: str | None = None,
    earliest: str | None = None,
    latest: str | None = None,
    count: int | None = None,
    fields: list[str] | None = None,
) -> tuple[list[dict], str]:
    """Execute oneshot search - implementation.

    Returns:
        Tuple of (results list, search SPL used)
    """
    defaults = get_search_defaults(profile)
    api_settings = get_api_settings(profile)

    earliest = earliest or defaults.get("earliest_time", "-24h")
    latest = latest or defaults.get("latest_time", "now")
    max_count = count or defaults.get("max_count", 50000)

    # Validate inputs
    spl = validate_spl(spl)
    earliest = validate_time_modifier(earliest)
    latest = validate_time_modifier(latest)

    # Build search
    search_spl = build_search(spl, earliest_time=earliest, latest_time=latest, fields=fields)

    # Get client
    client = get_splunk_client(profile=profile)

    # Execute oneshot search
    response = client.post(
        "/search/jobs/oneshot",
        data={
            "search": search_spl,
            "earliest_time": earliest,
            "latest_time": latest,
            "count": max_count,
            "output_mode": "json",
        },
        timeout=api_settings.get("search_timeout", 300),
        operation="oneshot search",
    )

    return response.get("results", []), search_spl


@search.command()
@click.argument("spl")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--earliest", "-e", help="Earliest time (e.g., -1h, -24h@h).")
@click.option("--latest", "-l", help="Latest time (e.g., now, -1h).")
@click.option("--count", "-c", type=int, help="Maximum number of results.")
@click.option("--fields", "-f", help="Comma-separated list of fields to return.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json", "csv"]),
    default="text",
    help="Output format.",
)
@click.option("--output-file", help="Write results to file (for csv).")
@click.pass_context
@handle_cli_errors
def oneshot(ctx, spl, profile, earliest, latest, count, fields, output, output_file):
    """Execute a oneshot search (results returned inline).

    Best for ad-hoc queries with results under 50,000 rows.

    Example:
        splunk-as search oneshot "index=main | stats count by sourcetype"
    """
    fields_list = parse_comma_list(fields)
    results, _ = _oneshot_impl(
        spl,
        profile=profile,
        earliest=earliest,
        latest=latest,
        count=count,
        fields=fields_list,
    )

    if output == "json":
        click.echo(format_json(results))
    elif output == "csv":
        if output_file:
            export_csv(results, output_file, columns=fields_list)
            print_success(f"Results written to {output_file}")
        else:
            click.echo(format_search_results(results, fields=fields_list, output_format="csv"))
    else:
        click.echo(format_search_results(results, fields=fields_list))
        print_success(f"Found {len(results)} results")


# -----------------------------------------------------------------------------
# Normal (async) search
# -----------------------------------------------------------------------------


def _normal_impl(
    spl: str,
    profile: str | None = None,
    earliest: str | None = None,
    latest: str | None = None,
) -> str:
    """Create a normal async search job - implementation.

    Returns:
        Search job ID (SID)
    """
    defaults = get_search_defaults(profile)

    earliest = earliest or defaults.get("earliest_time", "-24h")
    latest = latest or defaults.get("latest_time", "now")

    # Validate
    spl = validate_spl(spl)
    earliest = validate_time_modifier(earliest)
    latest = validate_time_modifier(latest)

    search_spl = build_search(spl, earliest_time=earliest, latest_time=latest)

    # Get client and create job
    client = get_splunk_client(profile=profile)

    response = client.post(
        "/search/v2/jobs",
        data={
            "search": search_spl,
            "exec_mode": "normal",
            "earliest_time": earliest,
            "latest_time": latest,
        },
        operation="create search job",
    )

    sid = response.get("sid")
    if not sid and "entry" in response:
        sid = response["entry"][0].get("name")

    return sid


@search.command()
@click.argument("spl")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--earliest", "-e", help="Earliest time.")
@click.option("--latest", "-l", help="Latest time.")
@click.option("--wait/--no-wait", default=False, help="Wait for job completion.")
@click.option("--timeout", type=int, default=300, help="Timeout in seconds.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def normal(ctx, spl, profile, earliest, latest, wait, timeout, output):
    """Execute a normal (async) search.

    Returns a search ID (SID) immediately. Use 'job status' to check progress.

    Example:
        splunk-as search normal "index=main | stats count" --wait
    """
    sid = _normal_impl(spl, profile=profile, earliest=earliest, latest=latest)

    if wait:
        client = get_splunk_client(profile=profile)
        wait_for_job(client, sid, timeout=timeout, show_progress=True)

        # Get results
        results_response = client.get(
            f"/search/v2/jobs/{sid}/results",
            params={"output_mode": "json", "count": 0},
            operation="get results",
        )
        results = results_response.get("results", [])

        if output == "json":
            click.echo(format_json({"sid": sid, "results": results}))
        else:
            click.echo(format_search_results(results))
            print_success(f"Completed: {len(results)} results")
    else:
        if output == "json":
            click.echo(format_json({"sid": sid, "status": "created"}))
        else:
            print_success(f"Job created: {sid}")
            click.echo(f"Use: splunk-as job status {sid}")


# -----------------------------------------------------------------------------
# Blocking search
# -----------------------------------------------------------------------------


def _blocking_impl(
    spl: str,
    profile: str | None = None,
    earliest: str | None = None,
    latest: str | None = None,
    timeout: int = 300,
) -> tuple[str, list[dict]]:
    """Execute blocking search - implementation.

    Returns:
        Tuple of (SID, results list)
    """
    defaults = get_search_defaults(profile)

    earliest = earliest or defaults.get("earliest_time", "-24h")
    latest = latest or defaults.get("latest_time", "now")

    # Validate
    spl = validate_spl(spl)
    earliest = validate_time_modifier(earliest)
    latest = validate_time_modifier(latest)

    search_spl = build_search(spl, earliest_time=earliest, latest_time=latest)

    client = get_splunk_client(profile=profile)

    # Create blocking job
    response = client.post(
        "/search/v2/jobs",
        data={
            "search": search_spl,
            "exec_mode": "blocking",
            "earliest_time": earliest,
            "latest_time": latest,
        },
        timeout=timeout,
        operation="blocking search",
    )

    # Extract SID
    sid = None
    if "entry" in response:
        sid = response["entry"][0].get("name")

    # Get results
    results_response = client.get(
        f"/search/v2/jobs/{sid}/results",
        params={"output_mode": "json", "count": 0},
        operation="get results",
    )

    return sid, results_response.get("results", [])


@search.command()
@click.argument("spl")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--earliest", "-e", help="Earliest time.")
@click.option("--latest", "-l", help="Latest time.")
@click.option("--timeout", type=int, default=300, help="Timeout in seconds.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def blocking(ctx, spl, profile, earliest, latest, timeout, output):
    """Execute a blocking search (waits for completion).

    Example:
        splunk-as search blocking "index=main | head 10" --timeout 60
    """
    sid, results = _blocking_impl(
        spl,
        profile=profile,
        earliest=earliest,
        latest=latest,
        timeout=timeout,
    )

    if output == "json":
        click.echo(format_json({"sid": sid, "results": results}))
    else:
        click.echo(format_search_results(results))
        print_success(f"Completed: {len(results)} results")


# -----------------------------------------------------------------------------
# Validate SPL
# -----------------------------------------------------------------------------


def _validate_impl(spl: str, suggestions: bool = False) -> dict:
    """Validate SPL syntax - implementation.

    Returns:
        Dict with validation results
    """
    is_valid, issues = validate_spl_syntax(spl)
    commands = parse_spl_commands(spl)
    complexity = estimate_search_complexity(spl)
    _, optimization_suggestions = optimize_spl(spl)

    return {
        "valid": is_valid,
        "issues": issues,
        "commands": [{"name": c[0], "args": c[1]} for c in commands],
        "complexity": complexity,
        "suggestions": optimization_suggestions if suggestions else [],
    }


@search.command()
@click.argument("spl")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--suggestions", "-s", is_flag=True, help="Show optimization suggestions.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def validate(ctx, spl, profile, suggestions, output):
    """Validate SPL syntax without executing.

    Example:
        splunk-as search validate "index=main | stats count"
    """
    result = _validate_impl(spl, suggestions=suggestions)

    if output == "json":
        click.echo(format_json(result))
    else:
        if result["valid"]:
            print_success("SPL syntax is valid")
        else:
            print_warning("SPL syntax issues found:")
            for issue in result["issues"]:
                click.echo(f"  - {issue}")

        click.echo(f"\nComplexity: {result['complexity']}")
        click.echo(f"Commands: {' | '.join(c['name'] for c in result['commands'])}")

        if suggestions and result["suggestions"]:
            click.echo("\nOptimization suggestions:")
            for s in result["suggestions"]:
                click.echo(f"  - {s}")


# -----------------------------------------------------------------------------
# Get results
# -----------------------------------------------------------------------------


def _results_impl(
    sid: str,
    profile: str | None = None,
    count: int = 0,
    offset: int = 0,
    fields: list[str] | None = None,
) -> list[dict]:
    """Get results from a completed job - implementation.

    Returns:
        List of result records
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)

    params = {
        "output_mode": "json",
        "count": count,
        "offset": offset,
    }

    if fields:
        params["field_list"] = ",".join(fields)

    response = client.get(
        f"/search/v2/jobs/{sid}/results",
        params=params,
        operation="get results",
    )

    return response.get("results", [])


@search.command()
@click.argument("sid")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--count", "-c", type=int, default=0, help="Maximum results to return (0=all).")
@click.option("--offset", type=int, default=0, help="Offset for pagination.")
@click.option("--fields", "-f", help="Comma-separated fields to return.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json", "csv"]),
    default="text",
    help="Output format.",
)
@click.option("--output-file", help="Write results to file.")
@click.pass_context
@handle_cli_errors
def results(ctx, sid, profile, count, offset, fields, output, output_file):
    """Get results from a completed search job.

    Example:
        splunk-as search results 1703779200.12345 --count 100
    """
    fields_list = parse_comma_list(fields)
    result_data = _results_impl(
        sid,
        profile=profile,
        count=count,
        offset=offset,
        fields=fields_list,
    )

    if output == "json":
        click.echo(format_json(result_data))
    elif output == "csv":
        if output_file:
            export_csv(result_data, output_file, columns=fields_list)
            print_success(f"Written to {output_file}")
        else:
            click.echo(format_search_results(result_data, fields=fields_list, output_format="csv"))
    else:
        click.echo(format_search_results(result_data, fields=fields_list))
        print_success(f"Retrieved {len(result_data)} results")


# -----------------------------------------------------------------------------
# Get preview
# -----------------------------------------------------------------------------


def _preview_impl(
    sid: str,
    profile: str | None = None,
    count: int = 100,
) -> list[dict]:
    """Get preview results from a running job - implementation.

    Returns:
        List of preview result records
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)

    response = client.get(
        f"/search/v2/jobs/{sid}/results_preview",
        params={"output_mode": "json", "count": count},
        operation="get preview",
    )

    return response.get("results", [])


@search.command()
@click.argument("sid")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--count", "-c", type=int, default=100, help="Maximum results to return.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def preview(ctx, sid, profile, count, output):
    """Get preview results from a running search job.

    Example:
        splunk-as search preview 1703779200.12345
    """
    results = _preview_impl(sid, profile=profile, count=count)

    if output == "json":
        click.echo(format_json(results))
    else:
        click.echo(format_search_results(results))
        click.echo(f"Preview: {len(results)} results (job may still be running)")
