from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table


def format_bytes(num_bytes: int) -> str:
    """Formats a number of bytes into a human-readable string."""
    if num_bytes < 0:
        return f"-{format_bytes(-num_bytes)}"
    val = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if val < 1024.0:
            if unit == "B":
                return f"{int(val)} {unit}"
            return f"{val:.2f} {unit}"
        val /= 1024.0
    return f"{val:.2f} PB"



class BaseProgressReporter:
    """Base interface for progress reporting."""

    def on_batch_start(self, total_files: int) -> None:
        pass

    def on_file_start(self, relative_path: str, size: int) -> None:
        pass

    def on_file_done(
        self, relative_path: str, status: str, src_size: int, out_size: Optional[int]
    ) -> None:
        pass

    def on_batch_end(self) -> None:
        pass


class NullProgressReporter(BaseProgressReporter):
    """Silent progress reporter for quiet/headless execution and tests."""
    pass


class RichProgressReporter(BaseProgressReporter):
    """Interactive terminal progress reporter using Rich with live ETA and space stats."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.progress: Optional[Progress] = None
        self.task_id: Optional[int] = None

        self.total_files = 0
        self.processed_count = 0
        self.compressed_count = 0
        self.skipped_count = 0
        self.failed_count = 0

        self.total_src_bytes = 0
        self.total_out_bytes = 0
        self.saved_bytes = 0

    def on_batch_start(self, total_files: int) -> None:
        self.total_files = total_files
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("• ETA:"),
            TimeRemainingColumn(),
            TextColumn("{task.fields[stats]}", justify="right"),
            console=self.console,
            transient=False,
        )
        self.progress.start()
        self.task_id = self.progress.add_task(
            "Batch Progress",
            total=total_files,
            stats="• Saved: 0 B",
        )

    def on_file_start(self, relative_path: str, size: int) -> None:
        if self.progress and self.task_id is not None:
            self.progress.update(
                self.task_id,
                description=f"Processing [yellow]{relative_path}[/yellow]",
            )

    def on_file_done(
        self, relative_path: str, status: str, src_size: int, out_size: Optional[int]
    ) -> None:
        self.processed_count += 1
        if status == "compressed":
            self.compressed_count += 1
            self.total_src_bytes += src_size
            actual_out = out_size if out_size is not None else 0
            self.total_out_bytes += actual_out
            self.saved_bytes += src_size - actual_out
        elif status in ("skipped_larger", "pre_existing", "skipped_crf"):
            self.skipped_count += 1
        else:
            self.failed_count += 1

        if self.progress and self.task_id is not None:
            saved_str = format_bytes(self.saved_bytes)
            self.progress.update(
                self.task_id,
                advance=1,
                description="Batch Progress",
                stats=f"• Saved: {saved_str}",
            )

    def on_batch_end(self) -> None:
        if self.progress:
            self.progress.stop()
            self.progress = None

        # Render summary table
        table = Table(title="Batch Compression Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold green", justify="right")

        table.add_row("Total Files Scanned", str(self.total_files))
        table.add_row("Files Compressed", str(self.compressed_count))
        table.add_row("Files Skipped", str(self.skipped_count))
        table.add_row("Files Failed", str(self.failed_count))

        if self.compressed_count > 0:
            reduction_pct = (
                (self.saved_bytes / self.total_src_bytes * 100)
                if self.total_src_bytes > 0
                else 0.0
            )
            table.add_row("Original Size (Compressed Files)", format_bytes(self.total_src_bytes))
            table.add_row("New Size", format_bytes(self.total_out_bytes))
            table.add_row("Total Space Saved", f"{format_bytes(self.saved_bytes)} ({reduction_pct:.1f}%)")

        self.console.print(Panel(table, expand=False))
