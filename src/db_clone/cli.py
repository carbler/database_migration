"""CLI interface using Typer."""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console

from db_clone import __version__

app = typer.Typer(
    name="db-clone",
    help="Professional database cloning tool for PostgreSQL and MySQL.",
    no_args_is_help=True,
)
checkpoint_app = typer.Typer(help="Manage migration checkpoints.")
app.add_typer(checkpoint_app, name="checkpoint")

console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"db-clone {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass


@app.command()
def clone(
    source: str = typer.Option(
        "", "--source", "-s",
        help="Source database URL (e.g. postgresql://user:pass@host:5432/db).",
        envvar="DB_CLONE_SOURCE_URL",
    ),
    target: str = typer.Option(
        "", "--target", "-t",
        help="Target database URL.",
        envvar="DB_CLONE_TARGET_URL",
    ),
    strategy: str = typer.Option(
        "overwrite", "--strategy",
        help="Conflict strategy: fail, overwrite, skip.",
    ),
    batch_size: int = typer.Option(
        5000, "--batch-size", "-b",
        help="Rows per batch for data transfer.",
    ),
    resume: bool = typer.Option(
        False, "--resume", "-r",
        help="Resume from last checkpoint.",
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level",
        help="Logging level.",
    ),
    log_file: str = typer.Option(
        "db-clone.log", "--log-file",
        help="Log file path.",
    ),
    exclude_tables: str = typer.Option(
        "", "--exclude-tables",
        help="Comma-separated glob patterns of tables to exclude.",
    ),
    include_tables: str = typer.Option(
        "", "--include-tables",
        help="Comma-separated glob patterns of tables to include.",
    ),
    data_only: bool = typer.Option(
        False, "--data-only",
        help="Only transfer data (skip schema objects).",
    ),
    schema_only: bool = typer.Option(
        False, "--schema-only",
        help="Only copy schema (skip data transfer).",
    ),
) -> None:
    """Clone a database from source to target."""
    if not source or not target:
        console.print("[red]Both --source and --target are required.[/]")
        raise typer.Exit(1)

    from db_clone.config import Settings, validate_urls
    from db_clone.logging_config import setup_logging
    from db_clone.models import ConflictStrategy

    try:
        validate_urls(source, target)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)

    setup_logging(log_level, log_file)

    try:
        strategy_enum = ConflictStrategy(strategy)
    except ValueError:
        console.print(f"[red]Invalid strategy: {strategy}. Use: fail, overwrite, skip[/]")
        raise typer.Exit(1)

    settings = Settings(
        source_url=source,
        target_url=target,
        batch_size=batch_size,
        log_level=log_level,
        log_file=log_file,
        strategy=strategy_enum,
        resume=resume,
        exclude_tables=exclude_tables,
        include_tables=include_tables,
        data_only=data_only,
        schema_only=schema_only,
    )

    from db_clone.engine.orchestrator import Orchestrator

    orchestrator = Orchestrator(settings)
    result = orchestrator.run()

    if not result.success:
        raise typer.Exit(1)


@app.command()
def info(
    source: str = typer.Option(
        "", "--source", "-s",
        help="Database URL to inspect.",
        envvar="DB_CLONE_SOURCE_URL",
    ),
) -> None:
    """Show database information."""
    if not source:
        console.print("[red]--source is required.[/]")
        raise typer.Exit(1)

    from db_clone.connectors import create_connector
    from db_clone.progress import show_db_info

    try:
        connector = create_connector(source)
        with connector:
            db_info = connector.get_database_info()
            show_db_info(db_info)

            # Show object counts
            objects = connector.discover_all()
            from rich.table import Table
            table = Table(title="Object Counts")
            table.add_column("Type", style="bold")
            table.add_column("Count", justify="right")
            for otype, objs in objects.items():
                if objs:
                    table.add_row(otype.value, str(len(objs)))
            console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@app.command()
def validate(
    source: str = typer.Option(
        "", "--source", "-s",
        help="Source database URL.",
        envvar="DB_CLONE_SOURCE_URL",
    ),
    target: str = typer.Option(
        "", "--target", "-t",
        help="Target database URL.",
        envvar="DB_CLONE_TARGET_URL",
    ),
) -> None:
    """Validate that target matches source after cloning."""
    if not source or not target:
        console.print("[red]Both --source and --target are required.[/]")
        raise typer.Exit(1)

    from db_clone.connectors import create_connector
    from db_clone.engine.validator import Validator
    from db_clone.progress import show_validation_results

    try:
        src = create_connector(source)
        tgt = create_connector(target)
        with src, tgt:
            validator = Validator(src, tgt)
            result = validator.validate()
            checks = [(c.name, c.passed, c.details) for c in result.checks]
            show_validation_results(checks)

            if result.passed:
                console.print("\n[bold green]Validation PASSED[/]")
            else:
                console.print("\n[bold red]Validation FAILED[/]")
                raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@checkpoint_app.command("show")
def checkpoint_show() -> None:
    """Show current checkpoint state."""
    from db_clone.checkpoint import CheckpointManager
    from db_clone.progress import show_checkpoint_summary

    cp = CheckpointManager()
    if cp.load():
        show_checkpoint_summary(cp.get_summary())
    else:
        console.print("[dim]No checkpoint found.[/]")


@checkpoint_app.command("clear")
def checkpoint_clear() -> None:
    """Clear the current checkpoint."""
    from db_clone.checkpoint import CheckpointManager

    cp = CheckpointManager()
    cp.clear()
    console.print("[green]Checkpoint cleared.[/]")


if __name__ == "__main__":
    app()
