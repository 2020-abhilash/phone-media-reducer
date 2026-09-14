from pathlib import Path
import runpy
from unittest.mock import ANY, patch

from phone_media_reducer.cli import build_parser, main
from phone_media_reducer.progress import NullProgressReporter, RichProgressReporter


def test_build_parser_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.source == "D:\\Photos & Videos\\Abhilash\\Phone"
    assert args.dest == "D:\\Compressed_Videos"
    assert args.crf == 28
    assert args.db is None
    assert args.quiet is False


def test_build_parser_custom_args():
    parser = build_parser()
    args = parser.parse_args(["/path/src", "/path/dst", "--crf", "18", "--db", "/path/db.sqlite", "-q"])
    assert args.source == "/path/src"
    assert args.dest == "/path/dst"
    assert args.crf == 18
    assert args.db == Path("/path/db.sqlite")
    assert args.quiet is True


def test_cli_main_invocation():
    with patch("phone_media_reducer.cli.batch_compress_directory") as mock_batch:
        main(["/in", "/out", "--crf", "22", "--db", "/db.sqlite"])
        mock_batch.assert_called_once()
        kwargs = mock_batch.call_args.kwargs
        assert kwargs["source_dir"] == "/in"
        assert kwargs["output_dir"] == "/out"
        assert kwargs["target_crf"] == 22
        assert kwargs["db_path"] == Path("/db.sqlite")
        assert isinstance(kwargs["progress_reporter"], RichProgressReporter)


def test_cli_main_invocation_quiet():
    with patch("phone_media_reducer.cli.batch_compress_directory") as mock_batch:
        main(["/in", "/out", "-q"])
        mock_batch.assert_called_once()
        kwargs = mock_batch.call_args.kwargs
        assert isinstance(kwargs["progress_reporter"], NullProgressReporter)


def test_cli_run_as_main():
    with patch("sys.argv", ["phone-media-reducer"]):
        with patch("phone_media_reducer.pipeline.batch_compress_directory") as mock_batch:
            runpy.run_path("phone_media_reducer/cli.py", run_name="__main__")
            mock_batch.assert_called_once_with(
                source_dir="D:\\Photos & Videos\\Abhilash\\Phone",
                output_dir="D:\\Compressed_Videos",
                target_crf=28,
                db_path=None,
                progress_reporter=ANY,
            )
