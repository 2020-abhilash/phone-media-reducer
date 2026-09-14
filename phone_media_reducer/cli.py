import argparse
from pathlib import Path
from typing import List, Optional

from phone_media_reducer.pipeline import batch_compress_directory
from phone_media_reducer.progress import NullProgressReporter, RichProgressReporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch compress phone media and preserve metadata."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="D:\\Photos & Videos\\Abhilash\\Phone",
        help="Source directory containing .mp4 files",
    )
    parser.add_argument(
        "dest",
        nargs="?",
        default="D:\\Compressed_Videos",
        help="Destination directory for compressed files",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=28,
        help="Constant Rate Factor (CRF) quality parameter (default: 28)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to SQLite tracking database (default: media_reducer.db)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Disable interactive progress bar and summary",
    )
    return parser


def main(args: Optional[List[str]] = None) -> None:
    parser = build_parser()
    parsed_args = parser.parse_args(args)
    reporter = NullProgressReporter() if parsed_args.quiet else RichProgressReporter()
    batch_compress_directory(
        source_dir=parsed_args.source,
        output_dir=parsed_args.dest,
        target_crf=parsed_args.crf,
        db_path=parsed_args.db,
        progress_reporter=reporter,
    )


if __name__ == "__main__":
    main()
