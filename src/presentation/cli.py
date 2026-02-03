import click
import structlog
from typing import Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table as RichTable
import os

from src.infrastructure.config.settings import Settings
from src.infrastructure.config.logging_config import configure_logging
from src.application.services.migration_service import MigrationService
from src.core.domain.interfaces import MigrationObserver
from src.core.domain.value_objects import DatabaseType

console = Console()
configure_logging()
logger = structlog.get_logger()

class RichObserver(MigrationObserver):
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        )
        self.total_task = None
        self.table_tasks = {}
        self.started = False

    def on_start(self, total_tables: int) -> None:
        self.progress.start()
        self.total_task = self.progress.add_task("Migrating tables...", total=total_tables)
        self.started = True

    def on_table_start(self, table_name: str, total_rows: int) -> None:
        task_id = self.progress.add_task(f"Table {table_name}", total=total_rows)
        self.table_tasks[table_name] = task_id

    def on_batch_processed(self, table_name: str, row_count: int) -> None:
        if table_name in self.table_tasks:
            self.progress.update(self.table_tasks[table_name], completed=row_count)

    def on_table_complete(self, table_name: str, duration: float) -> None:
        if table_name in self.table_tasks:
            self.progress.update(self.table_tasks[table_name], completed=self.progress.tasks[self.table_tasks[table_name]].total)
            self.progress.remove_task(self.table_tasks[table_name]) # Remove finished table task to clear screen? Or keep it?
            # Keeping it might clutter if many tables. Let's keep it for now or make it invisible.

        if self.total_task is not None:
            self.progress.advance(self.total_task)

    def on_error(self, table_name: str, error: str) -> None:
        console.print(f"[bold red]Error migrating {table_name}: {error}[/bold red]")

    def on_complete(self, stats: Any) -> None:
        if self.started:
            self.progress.stop()

        console.print("[bold green]Migration completed![/bold green]")

        if stats:
            # Stats is ValidationReport
            table = RichTable(title="Validation Report")
            table.add_column("Table", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Rows (Source/Target)", style="magenta")

            for table_name, counts in stats.row_counts.items():
                status = "✅ OK" if counts['source'] == counts['target'] else "❌ Mismatch"
                style = "green" if counts['source'] == counts['target'] else "red"
                table.add_row(
                    table_name,
                    f"[{style}]{status}[/{style}]",
                    f"{counts['source']} / {counts['target']}"
                )

            console.print(table)

            if stats.errors:
                console.print("[bold red]Errors found during validation:[/bold red]")
                for error in stats.errors:
                    console.print(f"[red]- {error}[/red]")
            elif stats.success:
                 console.print("[bold green]All validation checks passed![/bold green]")

@click.group()
@click.version_option(version='1.0.0')
def cli():
    """DB Migrator - Professional Database Migration Tool"""
    pass

@cli.command()
@click.option('--config', default='.env', help='Path to .env file (not used directly, loaded by decouple)')
@click.option('--validate/--no-validate', default=None, help='Validate after migration')
@click.option('--strategy', type=click.Choice(['fail', 'overwrite', 'skip', 'merge']), default=None)
@click.option('--batch-size', type=int, help='Override batch size')
@click.option('--workers', type=int, help='Override max workers')
def migrate(config, validate, strategy, batch_size, workers):
    """Migrate database from source to target"""
    console.print("[bold blue]Starting database migration...[/bold blue]")

    # Override settings
    if validate is not None:
        Settings.ENABLE_VALIDATION = validate
    if strategy:
        Settings.CONFLICT_STRATEGY = strategy
    if batch_size:
        Settings.BATCH_SIZE = batch_size
    if workers:
        Settings.MAX_WORKERS = workers

    observer = RichObserver()
    service = MigrationService(observer=observer)

    try:
        service.migrate()
    except Exception as e:
        console.print(f"[bold red]Fatal Error: {e}[/bold red]")
        # logger.exception(e) # Already logged by service? No, service re-raises critical ones.
        import traceback
        traceback.print_exc()

@cli.command()
def info():
    """Show supported databases and configuration"""
    table = RichTable(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Source DB Type", Settings.SOURCE_DB_TYPE)
    table.add_row("Source Host", Settings.SOURCE_DB_HOST)
    table.add_row("Source DB", Settings.SOURCE_DB_NAME)

    table.add_row("Target DB Type", Settings.TARGET_DB_TYPE)
    table.add_row("Target Host", Settings.TARGET_DB_HOST)
    table.add_row("Target DB", Settings.TARGET_DB_NAME)

    table.add_row("Strategy", Settings.CONFLICT_STRATEGY)
    table.add_row("Batch Size", str(Settings.BATCH_SIZE))
    table.add_row("Workers", str(Settings.MAX_WORKERS))

    console.print(table)

if __name__ == '__main__':
    cli()
