"""Rich UI components for progress display."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from db_clone.models import MigrationResult, PhaseStatus

console = Console()


def create_phase_progress() -> Progress:
    """Create a progress bar for phase-level tracking."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def create_data_progress() -> Progress:
    """Create a progress bar for row-level data transfer."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]rows"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def show_db_info(info: dict[str, Any]) -> None:
    """Display database info in a Rich panel."""
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key, value in info.items():
        if key == "size_bytes":
            value = _format_bytes(value)
            key = "size"
        table.add_row(str(key), str(value))

    console.print(Panel(table, title="Database Info", border_style="blue"))


def show_migration_summary(result: MigrationResult) -> None:
    """Display migration result summary."""
    table = Table(title="Migration Summary", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    status_style = "green" if result.success else "red"
    table.add_row("Status", f"[{status_style}]{'SUCCESS' if result.success else 'FAILED'}[/]")
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    table.add_row("Phases completed", str(result.phases_completed))
    table.add_row("Phases failed", str(result.phases_failed))
    table.add_row("Objects copied", str(result.objects_copied))
    table.add_row("Objects failed", str(result.objects_failed))
    table.add_row("Rows copied", f"{result.rows_copied:,}")

    console.print(table)

    if result.errors:
        console.print("\n[bold red]Errors:[/]")
        for err in result.errors[:10]:
            console.print(f"  [red]- {err}[/]")
        if len(result.errors) > 10:
            console.print(f"  [dim]... and {len(result.errors) - 10} more[/]")


def show_validation_results(checks: list[tuple[str, bool, str]]) -> None:
    """Display validation results."""
    table = Table(title="Validation Results")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for name, passed, details in checks:
        status = "[green]PASS[/]" if passed else "[red]FAIL[/]"
        table.add_row(name, status, details)

    console.print(table)


def show_checkpoint_summary(summary: dict[str, Any]) -> None:
    """Display checkpoint state."""
    console.print(f"\n[bold]Migration ID:[/] {summary.get('migration_id', 'N/A')}")

    phases = summary.get("phases", {})
    if not phases:
        console.print("[dim]No checkpoint data found.[/]")
        return

    table = Table(title="Checkpoint State")
    table.add_column("Phase", style="bold")
    table.add_column("Status")
    table.add_column("Completed")
    table.add_column("Failed")

    for name, data in phases.items():
        status = data["status"]
        style = {
            "completed": "green",
            "in_progress": "yellow",
            "failed": "red",
        }.get(status, "dim")
        table.add_row(
            name,
            f"[{style}]{status}[/]",
            str(data["objects_completed"]),
            str(data["objects_failed"]),
        )

    console.print(table)


def _format_bytes(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
