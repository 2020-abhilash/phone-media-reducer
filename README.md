# Phone Media Reducer 📱🎬

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/)

An intelligent, batch video compression and storage optimization tool for phone backups. It compresses high-bitrate phone videos to **H.265 (HEVC)**, saving **~50% storage** while preserving full visual quality, all internal metadata (EXIF / QuickTime), and exact filesystem creation/modification timestamps.

---

## 🌟 Key Features

- **High-Efficiency H.265 Encoding**: Encodes videos with `libx265` at a default Constant Rate Factor (**CRF 28**), matching the visual fidelity of x264 CRF 23 while cutting file sizes roughly in half.
- **Picture (Image) Compression**: Compresses photos and pictures using FFmpeg:
  - **JPEG (`.jpg`, `.jpeg`)**: High-quality compression using `-q:v` (default: `3`, customizable).
  - **PNG (`.png`)**: Lossless optimization using `-pred mixed` and `-compression_level 9`.
  - **WebP (`.webp`)**: Compressed using `libwebp` encoder.
- **Apple & Windows Playback Compatibility**: Automatically applies `-tag:v hvc1` for videos, enabling native hardware-accelerated playback in Apple QuickTime, iOS/macOS Photos, and Windows Media Player (preventing black-screen issues caused by `hev1` FourCC tags).
- **100% Metadata & Date Preservation**:
  - **Internal Tags**: Transfers all EXIF, QuickTime, GPS coordinates, camera model, and rotation tags via ExifTool.
  - **Filesystem Timestamps**: Preserves both **Date Created** and **Date Modified** on Windows, macOS, and Linux filesystems.
- **Intelligent Skip Logic**:
  - Probes video codec and encoder CRF settings prior to compression.
  - Automatically skips videos that are already H.265 with CRF $\ge 28$ or H.264 with CRF $\ge 28$.
  - Automatically processes uncompressed camera captures (no CRF), low-CRF videos, and other codecs (ProRes, VP9, etc.).
- **Resumable SQLite State Tracking**:
  - Remembers processed files across sessions using SHA-256 hashing and file sizes.
  - Idempotent: Safely stop and resume large directory jobs anytime without recompressing unchanged files.
- **Size Safety Guarantee**: If an output file (video or photo) ends up larger than the original, the output is discarded, keeping the original to avoid wasting storage.
- **Interactive Rich Progress UI**: Displays live file counts, percentage bars, elapsed time, estimated time of arrival (ETA), dynamic space saved, and an end-of-run summary table.

---

## 📋 System Prerequisites

Before running `phone-media-reducer`, ensure the following external tools are installed and accessible on your system `PATH`:

1. **[FFmpeg](https://ffmpeg.org/)** (with `libx265` and `ffprobe`):
   - **Windows** (via winget or chocolatey):
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - **macOS** (via Homebrew):
     ```bash
     brew install ffmpeg
     ```
   - **Linux** (Debian/Ubuntu):
     ```bash
     sudo apt update && sudo apt install ffmpeg
     ```
2. **[ExifTool](https://exiftool.org/)** (by Phil Harvey):
   - **Windows** (via winget or chocolatey):
     ```powershell
     winget install OliverBetz.ExifTool
     ```
   - **macOS**:
     ```bash
     brew install exiftool
     ```
   - **Linux**:
     ```bash
     sudo apt install libimage-exiftool-perl
     ```

---

## 🚀 Installation

### Using `uv` (Recommended)

```bash
# Clone the repository
git clone https://github.com/2020-abhilash/phone-media-reducer.git
cd phone-media-reducer

# Install dependencies and create environment
uv sync
```

### Using `pip`

```bash
pip install .
```

---

## 💻 Usage

### Command Line Interface (CLI)

```bash
# Basic run with default directories
phone-media-reducer

# Specify custom source and destination directories
phone-media-reducer "D:\Photos & Videos\Phone" "D:\Compressed_Videos"

# Customize CRF for videos and quality scale for images
phone-media-reducer /path/to/source /path/to/dest --crf 26 --image-quality 4

# Process pictures only (skip videos)
phone-media-reducer /path/to/source /path/to/dest --no-videos

# Process videos only (skip pictures)
phone-media-reducer /path/to/source /path/to/dest --no-images

# Specify a custom SQLite database path
phone-media-reducer /path/to/source /path/to/dest --db /path/to/tracker.db

# Headless / quiet mode (disables interactive rich progress bar)
phone-media-reducer /path/to/source /path/to/dest -q
```

#### CLI Options

| Argument | Description | Default |
| :--- | :--- | :--- |
| `source` | Source directory containing media files | `D:\Photos & Videos\Abhilash\Phone` |
| `dest` | Destination directory for compressed files | `D:\Compressed_Videos` |
| `--crf` | Constant Rate Factor quality parameter for videos | `28` |
| `--image-quality` | Quality scale for JPEG compression (`1-31`, lower is higher quality) | `3` |
| `--no-videos` | Skip video compression and only process pictures | `False` |
| `--no-images` | Skip picture compression and only process videos | `False` |
| `--db` | Path to SQLite tracking database | `media_reducer.db` |
| `-q`, `--quiet` | Run silently without interactive terminal progress | `False` |

---

### Python API

You can import and integrate the reduction pipeline directly into your Python scripts:

```python
from pathlib import Path
from phone_media_reducer import batch_compress_directory, MediaReducerPipeline

# Simple one-line batch compression for all media
batch_compress_directory(
    source_dir=Path("/media/phone_backup"),
    output_dir=Path("/media/compressed"),
    target_crf=28,
    image_quality=3,
    include_videos=True,
    include_images=True,
)

# Advanced usage with custom pipeline injection
from phone_media_reducer.db import MediaTracker
from phone_media_reducer.progress import RichProgressReporter

with MediaTracker("my_backup.db") as tracker:
    pipeline = MediaReducerPipeline(
        tracker=tracker,
        progress_reporter=RichProgressReporter(),
    )
    pipeline.process_directory(
        source_dir=Path("/media/phone_backup"),
        output_dir=Path("/media/compressed"),
        target_crf=28,
    )
```

---

## 🧠 Intelligent Codec & CRF Rules

Phone media contains various formats: camera raw captures, downloads, screen recordings, and prior exports. The pipeline probes the codec and encoding metadata before compressing:

| Detected Codec | Detected CRF | Action Taken | Reason |
| :--- | :--- | :--- | :--- |
| **H.265 / HEVC** | $\ge 28$ | **Skip** (`skipped_crf`) | Already sufficiently compressed. |
| **H.265 / HEVC** | $< 28$ | **Compress to H.265 CRF 28** | Significant space savings possible. |
| **H.264 / AVC** | $\ge 28$ | **Skip** (`skipped_crf`) | Heavily compressed; re-encoding causes generational loss. |
| **H.264 / AVC** | $< 28$ | **Compress to H.265 CRF 28** | ~50% space savings with matched fidelity. |
| **Any Codec** | None (Raw phone video) | **Compress to H.265 CRF 28** | Default camera files benefit most from reduction. |
| **Other Codecs** | Any / None (ProRes, VP9, etc.) | **Compress to H.265 CRF 28** | Re-encode to space-efficient standard. |

---

## 🏗️ Architecture

```
phone_media_reducer/
├── __init__.py          # Public package interface
├── cli.py               # Argument parsing and CLI entry point
├── db.py                # SQLite MediaTracker (hashes, sizes, statuses, and schema migrations)
├── encoder.py           # FFmpeg H.265 compression, FourCC hvc1 tag, and CRF probing
├── metadata.py          # ExifTool metadata & filesystem timestamp sync
├── pipeline.py          # Core processing pipeline orchestrator
├── progress.py          # Rich terminal progress bars, ETA, and summary tables
└── utils.py             # SHA-256 chunked hashing helper
```

---

## 🧪 Testing & Code Coverage

The test suite features **100% statement and branch test coverage** across all modules using `pytest` and `pytest-cov`.

Run tests:
```bash
uv run pytest
```

Output:
```text
Name                              Stmts   Miss Branch BrPart  Cover
-------------------------------------------------------------------
phone_media_reducer\__init__.py       7      0      0      0   100%
phone_media_reducer\cli.py           23      0      2      0   100%
phone_media_reducer\db.py            46      0      4      0   100%
phone_media_reducer\encoder.py       67      0     20      0   100%
phone_media_reducer\metadata.py       8      0      0      0   100%
phone_media_reducer\pipeline.py     106      0     32      0   100%
phone_media_reducer\progress.py      79      0     20      0   100%
phone_media_reducer\utils.py          9      0      2      0   100%
-------------------------------------------------------------------
TOTAL                               345      0     80      0   100%
============================= 37 passed in 3.87s ====================
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.
