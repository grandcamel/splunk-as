"""Job management commands for Splunk Assistant Skills CLI."""

from __future__ import annotations

import click

from splunk_assistant_skills_lib import (
    build_search,
    cancel_job,
    delete_job,
    finalize_job,
    format_job_status,
    format_json,
    format_table,
    get_dispatch_state,
    get_search_defaults,
    get_splunk_client,
    list_jobs,
    pause_job,
    print_success,
    set_job_ttl,
    unpause_job,
    validate_sid,
    validate_spl,
    validate_time_modifier,
    wait_for_job,
)

from ..cli_utils import handle_cli_errors


@click.group()
def job():
    """Search job lifecycle management.

    Create, monitor, control, and clean up Splunk search jobs.
    """
    pass


# -----------------------------------------------------------------------------
# Create job
# -----------------------------------------------------------------------------


def _create_impl(
    spl: str,
    profile: str | None = None,
    earliest: str | None = None,
    latest: str | None = None,
    exec_mode: str = "normal",
    app: str | None = None,
) -> dict:
    """Create a search job - implementation.

    Returns:
        Dict with job info (sid, search, times, mode)
    """
    defaults = get_search_defaults(profile)

    earliest = earliest or defaults.get("earliest_time", "-24h")
    latest = latest or defaults.get("latest_time", "now")

    # Validate inputs
    spl = validate_spl(spl)
    earliest = validate_time_modifier(earliest)
    latest = validate_time_modifier(latest)

    # Build search with time bounds
    search_spl = build_search(spl, earliest_time=earliest, latest_time=latest)

    # Get client
    client = get_splunk_client(profile=profile)

    # Build request data
    data = {
        "search": search_spl,
        "exec_mode": exec_mode,
        "earliest_time": earliest,
        "latest_time": latest,
    }

    if app:
        data["namespace"] = app

    # Create job
    response = client.post(
        "/search/v2/jobs",
        data=data,
        timeout=(
            client.DEFAULT_SEARCH_TIMEOUT if exec_mode == "blocking" else client.timeout
        ),
        operation="create search job",
    )

    # Extract SID
    sid = response.get("sid")
    if not sid and "entry" in response:
        sid = response["entry"][0].get(
            "name", response["entry"][0].get("content", {}).get("sid")
        )

    return {
        "sid": sid,
        "exec_mode": exec_mode,
        "search": search_spl,
        "earliest_time": earliest,
        "latest_time": latest,
    }


@job.command()
@click.argument("spl")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--earliest", "-e", help="Earliest time.")
@click.option("--latest", "-l", help="Latest time.")
@click.option(
    "--exec-mode",
    type=click.Choice(["normal", "blocking"]),
    default="normal",
    help="Execution mode.",
)
@click.option("--app", help="App context for search.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def create(ctx, spl, profile, earliest, latest, exec_mode, app, output):
    """Create a new search job.

    Example:
        splunk-as job create "index=main | stats count"
    """
    result = _create_impl(
        spl,
        profile=profile,
        earliest=earliest,
        latest=latest,
        exec_mode=exec_mode,
        app=app,
    )

    if output == "json":
        click.echo(format_json(result))
    else:
        print_success(f"Job created: {result['sid']}")
        search_display = result["search"][:80]
        if len(result["search"]) > 80:
            search_display += "..."
        click.echo(f"Search: {search_display}")
        click.echo(f"Mode: {result['exec_mode']}")
        click.echo(f"Time range: {result['earliest_time']} to {result['latest_time']}")


# -----------------------------------------------------------------------------
# Get job status
# -----------------------------------------------------------------------------


@job.command()
@click.argument("sid")
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
def status(ctx, sid, profile, output):
    """Get the status of a search job.

    Example:
        splunk-as job status 1703779200.12345
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)
    progress = get_dispatch_state(client, sid)

    if output == "json":
        click.echo(
            format_json(
                {
                    "sid": progress.sid,
                    "state": progress.state.value,
                    "progress": progress.progress_percent,
                    "event_count": progress.event_count,
                    "result_count": progress.result_count,
                    "scan_count": progress.scan_count,
                    "run_duration": progress.run_duration,
                    "is_done": progress.is_done,
                    "is_failed": progress.is_failed,
                    "is_paused": progress.is_paused,
                }
            )
        )
    else:
        click.echo(format_job_status({"content": progress.data}))


# -----------------------------------------------------------------------------
# List jobs
# -----------------------------------------------------------------------------


@job.command(name="list")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--count", "-c", type=int, default=50, help="Maximum jobs to list.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def list_jobs_cmd(ctx, profile, count, output):
    """List search jobs.

    Example:
        splunk-as job list --count 10
    """
    client = get_splunk_client(profile=profile)
    jobs = list_jobs(client, count=count)

    if output == "json":
        click.echo(format_json(jobs))
    else:
        if not jobs:
            click.echo("No active jobs found.")
            return

        # Format for display
        display_data = []
        for job_info in jobs:
            display_data.append(
                {
                    "SID": job_info.get("sid", "")[:30],
                    "State": job_info.get("dispatchState", "Unknown"),
                    "Progress": f"{float(job_info.get('doneProgress', 0)) * 100:.0f}%",
                    "Results": job_info.get("resultCount", 0),
                    "Duration": f"{float(job_info.get('runDuration', 0)):.1f}s",
                }
            )

        click.echo(
            format_table(
                display_data,
                columns=["SID", "State", "Progress", "Results", "Duration"],
            )
        )
        click.echo(f"\nTotal: {len(jobs)} jobs")


# -----------------------------------------------------------------------------
# Poll job
# -----------------------------------------------------------------------------


@job.command()
@click.argument("sid")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.option("--timeout", type=int, default=300, help="Timeout in seconds.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress updates.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
@handle_cli_errors
def poll(ctx, sid, profile, timeout, quiet, output):
    """Poll a job until completion.

    Example:
        splunk-as job poll 1703779200.12345 --timeout 60
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)

    progress = wait_for_job(
        client,
        sid,
        timeout=timeout,
        show_progress=not quiet,
    )

    if output == "json":
        click.echo(
            format_json(
                {
                    "sid": progress.sid,
                    "state": progress.state.value,
                    "result_count": progress.result_count,
                    "event_count": progress.event_count,
                    "run_duration": progress.run_duration,
                }
            )
        )
    else:
        print_success(f"Job completed: {progress.state.value}")
        click.echo(f"Results: {progress.result_count:,}")
        click.echo(f"Events: {progress.event_count:,}")
        click.echo(f"Duration: {progress.run_duration:.2f}s")


# -----------------------------------------------------------------------------
# Cancel job
# -----------------------------------------------------------------------------


@job.command()
@click.argument("sid")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.pass_context
@handle_cli_errors
def cancel(ctx, sid, profile):
    """Cancel a running search job.

    Example:
        splunk-as job cancel 1703779200.12345
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)
    cancel_job(client, sid)
    print_success(f"Job cancelled: {sid}")


# -----------------------------------------------------------------------------
# Pause job
# -----------------------------------------------------------------------------


@job.command()
@click.argument("sid")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.pass_context
@handle_cli_errors
def pause(ctx, sid, profile):
    """Pause a running search job.

    Example:
        splunk-as job pause 1703779200.12345
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)
    pause_job(client, sid)
    print_success(f"Job paused: {sid}")


# -----------------------------------------------------------------------------
# Unpause job
# -----------------------------------------------------------------------------


@job.command()
@click.argument("sid")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.pass_context
@handle_cli_errors
def unpause(ctx, sid, profile):
    """Resume a paused search job.

    Example:
        splunk-as job unpause 1703779200.12345
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)
    unpause_job(client, sid)
    print_success(f"Job resumed: {sid}")


# -----------------------------------------------------------------------------
# Finalize job
# -----------------------------------------------------------------------------


@job.command()
@click.argument("sid")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.pass_context
@handle_cli_errors
def finalize(ctx, sid, profile):
    """Finalize a search job (stop and return current results).

    Example:
        splunk-as job finalize 1703779200.12345
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)
    finalize_job(client, sid)
    print_success(f"Job finalized: {sid}")


# -----------------------------------------------------------------------------
# Delete job
# -----------------------------------------------------------------------------


@job.command()
@click.argument("sid")
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.pass_context
@handle_cli_errors
def delete(ctx, sid, profile):
    """Delete a search job.

    Example:
        splunk-as job delete 1703779200.12345
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)
    delete_job(client, sid)
    print_success(f"Job deleted: {sid}")


# -----------------------------------------------------------------------------
# Set TTL
# -----------------------------------------------------------------------------


@job.command()
@click.argument("sid")
@click.argument("ttl_value", type=int)
@click.option("--profile", "-p", help="Splunk profile to use.")
@click.pass_context
@handle_cli_errors
def ttl(ctx, sid, ttl_value, profile):
    """Set the TTL (time-to-live) for a search job.

    Example:
        splunk-as job ttl 1703779200.12345 3600
    """
    sid = validate_sid(sid)
    client = get_splunk_client(profile=profile)
    set_job_ttl(client, sid, ttl=ttl_value)
    print_success(f"Job TTL set to {ttl_value}s: {sid}")
