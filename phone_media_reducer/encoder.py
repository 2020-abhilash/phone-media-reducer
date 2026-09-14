from pathlib import Path
import re
import shutil
from typing import Optional, Tuple, Union

import ffmpeg


def compress_mp4(
    input_file: Union[str, Path],
    output_file: Union[str, Path],
    crf: int = 28,
    vcodec: str = "libx265",
) -> bool:
    """Compresses an MP4 file using H.265 (libx265) or custom codec, preserving tags and timestamps."""
    extra_args = {}
    if "265" in vcodec.lower() or "hevc" in vcodec.lower():
        extra_args["tag:v"] = "hvc1"

    try:
        (
            ffmpeg
            .input(str(input_file))
            .output(
                str(output_file),
                vcodec=vcodec,
                crf=crf,
                acodec="aac",
                map_metadata=0,
                movflags="use_metadata_tags",
                **extra_args,
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        shutil.copystat(str(input_file), str(output_file))
        return True
    except ffmpeg.Error as e:
        print("FFMpeg Error: ", e.stderr.decode("utf-8"))
        return False


def probe_codec_and_crf(
    file_path: Union[str, Path],
) -> Tuple[Optional[str], Optional[float]]:
    """Probes the video file for codec name and CRF metadata if present."""
    try:
        probe = ffmpeg.probe(str(file_path))
    except ffmpeg.Error:
        return None, None

    video_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
    if not video_streams:
        return None, None

    video_stream = video_streams[0]
    codec = video_stream.get("codec_name", "").lower() or None

    all_tags = {}
    all_tags.update(probe.get("format", {}).get("tags", {}))
    all_tags.update(video_stream.get("tags", {}))

    crf = None
    crf_pattern = re.compile(r"crf\s*=\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
    for val in all_tags.values():
        match = crf_pattern.search(str(val))
        if match:
            crf = float(match.group(1))
            break

    return codec, crf


def should_skip_based_on_crf(
    codec: Optional[str],
    crf: Optional[float],
    target_crf: int = 28,
) -> bool:
    """
    Evaluates whether a video should be skipped based on its existing codec and CRF:
    - H.265 (HEVC) with CRF >= target_crf (default 28) -> Skip
    - H.264 (AVC) with CRF >= 28 -> Skip (already heavily compressed)
    - All others (no CRF, CRF < threshold, other codecs) -> False (do not skip)
    """
    if crf is None or codec is None:
        return False

    codec_lower = codec.lower()
    if codec_lower in ("hevc", "h265") and crf >= target_crf:
        return True

    if codec_lower in ("h264", "avc") and crf >= 28:
        return True

    return False


def compress_image(
    input_file: Union[str, Path],
    output_file: Union[str, Path],
    quality_scale: int = 3,
) -> bool:
    """Compresses an image file (JPEG, PNG, WebP) using FFmpeg, preserving timestamps."""
    input_path = Path(input_file)
    suffix = input_path.suffix.lower()

    extra_args = {}
    if suffix in (".jpg", ".jpeg"):
        extra_args["q:v"] = quality_scale
    elif suffix == ".png":
        extra_args["pred"] = "mixed"
        extra_args["compression_level"] = 9
    elif suffix == ".webp":
        extra_args["vcodec"] = "libwebp"
        extra_args["quality"] = 80
    else:
        return False

    try:
        (
            ffmpeg
            .input(str(input_file))
            .output(str(output_file), **extra_args)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        shutil.copystat(str(input_file), str(output_file))
        return True
    except ffmpeg.Error as e:
        stderr_msg = e.stderr.decode("utf-8") if e.stderr else str(e)
        print("FFMpeg Error: ", stderr_msg)
        return False

