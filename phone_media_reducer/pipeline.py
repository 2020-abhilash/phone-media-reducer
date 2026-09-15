from pathlib import Path
from typing import Callable, Optional, Set, Union

from phone_media_reducer.db import MediaTracker
from phone_media_reducer.encoder import (
    compress_image,
    compress_mp4,
    probe_codec_and_crf,
    should_skip_based_on_crf,
)
from phone_media_reducer.metadata import copy_all_metadata
from phone_media_reducer.progress import BaseProgressReporter, NullProgressReporter
from phone_media_reducer.utils import compute_file_hash

VIDEO_EXTENSIONS: Set[str] = {".mp4", ".mov", ".m4v"}
IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_EXTENSIONS: Set[str] = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


class MediaReducerPipeline:
    """Orchestrates batch media compression with injected dependencies."""

    def __init__(
        self,
        tracker: MediaTracker,
        compressor: Callable[[Union[str, Path], Union[str, Path], int], bool] = compress_mp4,
        image_compressor: Callable[[Union[str, Path], Union[str, Path], int], bool] = compress_image,
        metadata_copier: Callable[[Union[str, Path], Union[str, Path]], None] = copy_all_metadata,
        hasher: Callable[[Union[str, Path]], str] = compute_file_hash,
        probe_func: Callable[[Union[str, Path]], tuple[Optional[str], Optional[float]]] = probe_codec_and_crf,
        progress_reporter: Optional[BaseProgressReporter] = None,
    ):
        self.tracker = tracker
        self.compressor = compressor
        self.image_compressor = image_compressor
        self.metadata_copier = metadata_copier
        self.hasher = hasher
        self.probe_func = probe_func
        self.progress_reporter = progress_reporter or NullProgressReporter()

    def process_directory(
        self,
        source_dir: Union[str, Path],
        output_dir: Union[str, Path],
        target_crf: int = 28,
        image_quality: int = 3,
        include_videos: bool = True,
        include_images: bool = True,
    ) -> None:
        """Finds all media files in source_dir and processes them into output_dir."""
        source_path = Path(source_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        allowed_extensions = set()
        if include_videos:
            allowed_extensions |= VIDEO_EXTENSIONS
        if include_images:
            allowed_extensions |= IMAGE_EXTENSIONS

        files = sorted(
            [f for f in source_path.rglob("*") if f.is_file() and f.suffix.lower() in allowed_extensions]
        )
        self.progress_reporter.on_batch_start(len(files))

        for input_file_path in files:
            relative_path = input_file_path.relative_to(source_path)
            output_file_path = output_path / relative_path
            self.process_file(
                input_file_path,
                output_file_path,
                str(relative_path),
                target_crf=target_crf,
                image_quality=image_quality,
            )

        self.progress_reporter.on_batch_end()
        print("Compression complete.")

    def process_file(
        self,
        input_file_path: Path,
        output_file_path: Path,
        relative_path_str: str,
        target_crf: int = 28,
        image_quality: int = 3,
    ) -> None:
        """Processes a single media file through validation, compression, and tracking."""
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        src_size = input_file_path.stat().st_size
        self.progress_reporter.on_file_start(relative_path_str, src_size)

        if self._handle_existing_output(input_file_path, output_file_path, relative_path_str, src_size):
            return

        if self._is_already_processed(input_file_path, relative_path_str, src_size):
            return

        is_video = input_file_path.suffix.lower() in VIDEO_EXTENSIONS
        param_value = target_crf if is_video else image_quality

        if is_video:
            if self._should_skip_source_crf(input_file_path, relative_path_str, target_crf, src_size):
                return
            compress_fn = lambda src, dst: self.compressor(src, dst, target_crf)
        else:
            compress_fn = lambda src, dst: self.image_compressor(src, dst, image_quality)

        self._compress_and_record(
            input_file_path,
            output_file_path,
            relative_path_str,
            param_value,
            src_size,
            compress_fn,
        )

    def _handle_existing_output(
        self, input_file_path: Path, output_file_path: Path, relative_path_str: str, src_size: int
    ) -> bool:
        """Checks if output file already exists in destination and records if needed."""
        if not output_file_path.exists():
            return False

        record = self.tracker.get_record(relative_path_str)
        out_size = output_file_path.stat().st_size
        if record is None:
            src_hash = self.hasher(input_file_path)
            self.tracker.save_record(relative_path_str, src_hash, src_size, out_size, "pre_existing", None)

        print(f"Skipping {input_file_path} as the output file already exists.")
        self.progress_reporter.on_file_done(relative_path_str, "pre_existing", src_size, out_size)
        return True

    def _is_already_processed(self, input_file_path: Path, relative_path_str: str, src_size: int) -> bool:
        """Checks if the file was previously processed and remains unchanged."""
        record = self.tracker.get_record(relative_path_str)
        if record is not None and record["status"] in ("compressed", "pre_existing", "skipped_larger", "skipped_crf"):
            if src_size == record["source_size"] and self.hasher(input_file_path) == record["source_hash"]:
                print(f"Skipping {input_file_path} as it was previously processed (status: {record['status']}).")
                self.progress_reporter.on_file_done(relative_path_str, record["status"], src_size, record["output_size"])
                return True
        return False

    def _should_skip_source_crf(
        self, input_file_path: Path, relative_path_str: str, target_crf: int, src_size: int
    ) -> bool:
        """Evaluates whether to skip compression based on source codec and CRF metadata."""
        codec, crf = self.probe_func(input_file_path)
        if should_skip_based_on_crf(codec, crf, target_crf):
            src_hash = self.hasher(input_file_path)
            self.tracker.save_record(relative_path_str, src_hash, src_size, None, "skipped_crf", target_crf)
            print(f"Skipping {input_file_path} as it is already compressed ({codec} with CRF {crf} >= threshold).")
            self.progress_reporter.on_file_done(relative_path_str, "skipped_crf", src_size, None)
            return True
        return False

    def _compress_and_record(
        self,
        input_file_path: Path,
        output_file_path: Path,
        relative_path_str: str,
        param_val: int,
        src_size: int,
        compress_fn: Optional[Callable[[Path, Path], bool]] = None,
    ) -> None:
        """Compresses file, checks size, transfers metadata, and persists result."""
        src_hash = self.hasher(input_file_path)
        actual_compress_fn = compress_fn or (lambda src, dst: self.compressor(src, dst, param_val))

        if actual_compress_fn(input_file_path, output_file_path):
            self.metadata_copier(input_file_path, output_file_path)
            out_size = output_file_path.stat().st_size
            if out_size > src_size:
                output_file_path.unlink()
                self.tracker.save_record(relative_path_str, src_hash, src_size, out_size, "skipped_larger", param_val)
                print(f"Deleted {output_file_path} as the output file is larger than the input file.")
                self.progress_reporter.on_file_done(relative_path_str, "skipped_larger", src_size, out_size)
            else:
                self.tracker.save_record(relative_path_str, src_hash, src_size, out_size, "compressed", param_val)
                self.progress_reporter.on_file_done(relative_path_str, "compressed", src_size, out_size)
        else:
            self.tracker.save_record(relative_path_str, src_hash, src_size, None, "failed", param_val)
            print(f"Failed to compress {input_file_path}")
            self.progress_reporter.on_file_done(relative_path_str, "failed", src_size, None)


def batch_compress_directory(
    source_dir: Union[str, Path],
    output_dir: Union[str, Path],
    target_crf: int = 28,
    image_quality: int = 3,
    include_videos: bool = True,
    include_images: bool = True,
    db_path: Optional[Union[str, Path]] = None,
    pipeline: Optional[MediaReducerPipeline] = None,
    progress_reporter: Optional[BaseProgressReporter] = None,
) -> None:
    """
    Convenience function to batch compress a directory.
    Instantiates MediaTracker and MediaReducerPipeline if not provided.
    """
    if pipeline is not None:
        pipeline.process_directory(
            source_dir,
            output_dir,
            target_crf=target_crf,
            image_quality=image_quality,
            include_videos=include_videos,
            include_images=include_images,
        )
        return

    if db_path is None:
        db_path = Path.cwd() / "media_reducer.db"

    reporter = progress_reporter or NullProgressReporter()

    with MediaTracker(db_path) as tracker:
        active_pipeline = MediaReducerPipeline(tracker=tracker, progress_reporter=reporter)
        active_pipeline.process_directory(
            source_dir,
            output_dir,
            target_crf=target_crf,
            image_quality=image_quality,
            include_videos=include_videos,
            include_images=include_images,
        )

