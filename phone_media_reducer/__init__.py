"""Phone Media Reducer: Batch compress phone media with metadata preservation and SQLite tracking."""

from phone_media_reducer.db import MediaTracker, get_record, init_db, save_record
from phone_media_reducer.encoder import (
    compress_mp4,
    probe_codec_and_crf,
    should_skip_based_on_crf,
)
from phone_media_reducer.metadata import copy_all_metadata
from phone_media_reducer.pipeline import MediaReducerPipeline, batch_compress_directory
from phone_media_reducer.progress import (
    BaseProgressReporter,
    NullProgressReporter,
    RichProgressReporter,
    format_bytes,
)
from phone_media_reducer.utils import compute_file_hash

__all__ = [
    "BaseProgressReporter",
    "MediaReducerPipeline",
    "MediaTracker",
    "NullProgressReporter",
    "RichProgressReporter",
    "batch_compress_directory",
    "compress_mp4",
    "compute_file_hash",
    "copy_all_metadata",
    "format_bytes",
    "get_record",
    "init_db",
    "probe_codec_and_crf",
    "save_record",
    "should_skip_based_on_crf",
]
