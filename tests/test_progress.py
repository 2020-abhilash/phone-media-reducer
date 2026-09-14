import io
from rich.console import Console

from phone_media_reducer.progress import (
    BaseProgressReporter,
    NullProgressReporter,
    RichProgressReporter,
    format_bytes,
)


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1536) == "1.50 KB"
    assert format_bytes(1048576) == "1.00 MB"
    assert format_bytes(1073741824) == "1.00 GB"
    assert format_bytes(1099511627776) == "1.00 TB"
    assert format_bytes(1125899906842624) == "1.00 PB"
    assert format_bytes(-1048576) == "-1.00 MB"


def test_base_and_null_progress_reporter():
    base = BaseProgressReporter()
    base.on_batch_start(10)
    base.on_file_start("video.mp4", 1000)
    base.on_file_done("video.mp4", "compressed", 1000, 500)
    base.on_batch_end()

    null_rep = NullProgressReporter()
    null_rep.on_batch_start(10)
    null_rep.on_file_start("video.mp4", 1000)
    null_rep.on_file_done("video.mp4", "compressed", 1000, 500)
    null_rep.on_batch_end()


def test_rich_progress_reporter_lifecycle():
    output = io.StringIO()
    console = Console(file=output, force_terminal=True, width=120)
    reporter = RichProgressReporter(console=console)

    reporter.on_batch_start(3)
    assert reporter.progress is not None

    reporter.on_file_start("videos/1.mp4", 1000)
    reporter.on_file_done("videos/1.mp4", "compressed", 1000, 400)

    reporter.on_file_start("videos/2.mp4", 500)
    reporter.on_file_done("videos/2.mp4", "skipped_larger", 500, 600)

    reporter.on_file_start("videos/3.mp4", 700)
    reporter.on_file_done("videos/3.mp4", "failed", 700, None)

    reporter.on_batch_end()
    assert reporter.progress is None

    captured = output.getvalue()
    assert "Batch Compression Summary" in captured
    assert "Total Files Scanned" in captured
    assert "Files Compressed" in captured
    assert "Total Space Saved" in captured


def test_rich_progress_reporter_no_compressed_files():
    output = io.StringIO()
    console = Console(file=output, force_terminal=True, width=120)
    reporter = RichProgressReporter(console=console)

    reporter.on_batch_start(1)
    reporter.on_file_done("videos/1.mp4", "pre_existing", 500, 500)
    reporter.on_batch_end()

    captured = output.getvalue()
    assert "Batch Compression Summary" in captured
    assert "Total Space Saved" not in captured


def test_rich_progress_reporter_zero_byte_compressed():
    output = io.StringIO()
    console = Console(file=output, force_terminal=True, width=120)
    reporter = RichProgressReporter(console=console)

    reporter.on_batch_start(1)
    reporter.on_file_done("empty.mp4", "compressed", 0, 0)
    reporter.on_batch_end()

    captured = output.getvalue()
    assert "Batch Compression Summary" in captured
    assert "Total Space Saved" in captured
    assert "(0.0%)" in captured


def test_rich_progress_reporter_inactive_guard():
    reporter = RichProgressReporter()
    # Calling update hooks before on_batch_start should safely no-op
    reporter.on_file_start("test.mp4", 100)
    reporter.on_file_done("test.mp4", "compressed", 100, 50)
    reporter.on_batch_end()
    assert reporter.processed_count == 1
