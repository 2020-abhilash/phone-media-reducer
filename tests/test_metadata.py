from pathlib import Path
from unittest.mock import MagicMock, patch

from phone_media_reducer.metadata import copy_all_metadata


def test_copy_all_metadata():
    source_file = "source/video.mp4"
    target_file = Path("dest/video.mp4")

    mock_et_instance = MagicMock()

    with patch("exiftool.ExifTool") as mock_exiftool:
        mock_exiftool.return_value.__enter__.return_value = mock_et_instance

        with patch("shutil.copystat") as mock_copystat:
            copy_all_metadata(source_file, target_file)

            mock_exiftool.return_value.__enter__.assert_called_once()
            mock_exiftool.return_value.__exit__.assert_called_once()
            mock_et_instance.execute.assert_called_once_with(
                "-TagsFromFile",
                source_file,
                "-all:all",
                "-FileCreateDate",
                "-FileModifyDate",
                "-overwrite_original",
                str(target_file),
            )
            mock_copystat.assert_called_once_with(str(source_file), str(target_file))


def test_copy_all_metadata_preserves_filesystem_timestamps(tmp_path):
    import exiftool
    src = tmp_path / "src.mp4"
    dst = tmp_path / "dst.mp4"
    src.write_bytes(b"dummy source")
    dst.write_bytes(b"dummy dest")

    with exiftool.ExifTool() as et:
        et.execute("-FileCreateDate=2019:05:01 10:00:00", "-FileModifyDate=2019:05:01 10:00:00", "-overwrite_original", str(src))

    copy_all_metadata(src, dst)

    assert dst.stat().st_mtime == src.stat().st_mtime
    assert dst.stat().st_ctime == src.stat().st_ctime

