import shutil
from pathlib import Path
from typing import Union

import exiftool


def copy_all_metadata(
    source_file: Union[str, Path],
    target_file: Union[str, Path],
) -> None:
    """Copies all metadata tags and file dates from source_file to target_file using ExifTool."""
    with exiftool.ExifTool() as et:
        et.execute(
            "-TagsFromFile",
            str(source_file),
            "-all:all",
            "-FileCreateDate",
            "-FileModifyDate",
            "-overwrite_original",
            str(target_file),
        )
    shutil.copystat(str(source_file), str(target_file))
