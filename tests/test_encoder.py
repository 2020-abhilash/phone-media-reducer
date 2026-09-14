from unittest.mock import MagicMock, patch

import ffmpeg

from phone_media_reducer.encoder import (
    compress_mp4,
    probe_codec_and_crf,
    should_skip_based_on_crf,
)


def test_compress_mp4_default_hevc_success():
    input_file = "source/sample.mp4"
    output_file = "dest/sample.mp4"

    mock_input = MagicMock()
    mock_output = MagicMock()
    mock_overwrite = MagicMock()

    with patch("ffmpeg.input", return_value=mock_input) as mock_ffmpeg_input, \
         patch("shutil.copystat") as mock_copystat:
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run.return_value = (b"", b"")

        # Test defaults: crf=28, vcodec="libx265", tag:v="hvc1"
        result = compress_mp4(input_file, output_file)

        assert result is True
        mock_ffmpeg_input.assert_called_once_with(input_file)
        mock_input.output.assert_called_once_with(
            output_file,
            vcodec="libx265",
            crf=28,
            acodec="aac",
            map_metadata=0,
            movflags="use_metadata_tags",
            **{"tag:v": "hvc1"},
        )
        mock_output.overwrite_output.assert_called_once()
        mock_overwrite.run.assert_called_once_with(capture_stdout=True, capture_stderr=True)
        mock_copystat.assert_called_once_with(input_file, output_file)


def test_compress_mp4_custom_codec():
    input_file = "source/sample.mp4"
    output_file = "dest/sample.mp4"

    mock_input = MagicMock()
    mock_output = MagicMock()
    mock_overwrite = MagicMock()

    with patch("ffmpeg.input", return_value=mock_input), \
         patch("shutil.copystat"):
        mock_input.output.return_value = mock_output
        mock_output.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run.return_value = (b"", b"")

        # Custom codec (libx264) without hvc1 tag
        result = compress_mp4(input_file, output_file, crf=23, vcodec="libx264")

        assert result is True
        mock_input.output.assert_called_once_with(
            output_file,
            vcodec="libx264",
            crf=23,
            acodec="aac",
            map_metadata=0,
            movflags="use_metadata_tags",
        )


def test_compress_mp4_ffmpeg_error(capsys):
    input_file = "source/error.mp4"
    output_file = "dest/error.mp4"

    error = ffmpeg.Error(cmd="ffmpeg", stdout=b"", stderr=b"Encoder error occurred")

    with patch("ffmpeg.input", side_effect=error), \
         patch("shutil.copystat") as mock_copystat:
        result = compress_mp4(input_file, output_file, crf=28)

        assert result is False
        mock_copystat.assert_not_called()
        captured = capsys.readouterr()
        assert "FFMpeg Error:  Encoder error occurred" in captured.out


def test_probe_codec_and_crf():
    # 1. Successful probe with HEVC and CRF in stream tags
    mock_probe_hevc = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "hevc",
                "tags": {"ENCODER_SETTINGS": "x265 - crf=28.0 - preset medium"},
            }
        ],
        "format": {"tags": {}},
    }
    with patch("ffmpeg.probe", return_value=mock_probe_hevc):
        codec, crf = probe_codec_and_crf("test_hevc.mp4")
        assert codec == "hevc"
        assert crf == 28.0

    # 2. Successful probe with H.264 and CRF in format tags
    mock_probe_h264 = {
        "streams": [{"codec_type": "video", "codec_name": "h264", "tags": {}}],
        "format": {"tags": {"comment": "x264 core 157 - crf=23 - rc=crf"}},
    }
    with patch("ffmpeg.probe", return_value=mock_probe_h264):
        codec, crf = probe_codec_and_crf("test_h264.mp4")
        assert codec == "h264"
        assert crf == 23.0

    # 3. Probe with video stream having metadata tags but no CRF (phone camera recording)
    mock_probe_phone = {
        "streams": [{"codec_type": "video", "codec_name": "hevc", "tags": {"rotate": "90", "creation_time": "2024-01-01"}}],
        "format": {"tags": {"major_brand": "mp42"}},
    }
    with patch("ffmpeg.probe", return_value=mock_probe_phone):
        codec, crf = probe_codec_and_crf("phone.mp4")
        assert codec == "hevc"
        assert crf is None

    # 4. Probe with no video stream (audio only)
    mock_probe_audio = {
        "streams": [{"codec_type": "audio", "codec_name": "aac"}],
        "format": {},
    }
    with patch("ffmpeg.probe", return_value=mock_probe_audio):
        codec, crf = probe_codec_and_crf("audio.mp4")
        assert codec is None
        assert crf is None

    # 5. FFmpeg probe error
    with patch("ffmpeg.probe", side_effect=ffmpeg.Error("probe", b"", b"error")):
        codec, crf = probe_codec_and_crf("bad.mp4")
        assert codec is None
        assert crf is None


def test_should_skip_based_on_crf():
    # H.265 at or above target (28)
    assert should_skip_based_on_crf("hevc", 28.0, target_crf=28) is True
    assert should_skip_based_on_crf("h265", 30.0, target_crf=28) is True

    # H.265 below target
    assert should_skip_based_on_crf("hevc", 22.0, target_crf=28) is False

    # H.264 at or above 28 (already heavily compressed)
    assert should_skip_based_on_crf("h264", 28.0, target_crf=28) is True
    assert should_skip_based_on_crf("avc", 30.0, target_crf=28) is True

    # H.264 below 28 (e.g. 23) -> can benefit from H.265
    assert should_skip_based_on_crf("h264", 23.0, target_crf=28) is False

    # Other codecs (e.g. ProRes, VP9) -> do not skip based on CRF
    assert should_skip_based_on_crf("prores", 28.0, target_crf=28) is False

    # None values
    assert should_skip_based_on_crf(None, 28.0, target_crf=28) is False
    assert should_skip_based_on_crf("hevc", None, target_crf=28) is False
