import hashlib
from pathlib import Path
from unittest.mock import MagicMock

from phone_media_reducer.db import MediaTracker
from phone_media_reducer.pipeline import MediaReducerPipeline, batch_compress_directory


def test_batch_compress_pre_existing_files(tmp_path, capsys):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    db_path = tmp_path / "test.db"

    source_dir.mkdir(parents=True)
    input_file = source_dir / "pre.mp4"
    input_file.write_bytes(b"original source content")

    output_file = output_dir / "pre.mp4"
    output_file.parent.mkdir(parents=True)
    output_file.write_bytes(b"pre-existing output content")

    # Run 1: Pre-existing file not in DB -> records pre_existing info in DB and skips
    batch_compress_directory(source_dir, output_dir, db_path=db_path)

    with MediaTracker(db_path) as tracker:
        record = tracker.get_record("pre.mp4")

    assert record is not None
    assert record["status"] == "pre_existing"
    assert record["source_size"] == len(b"original source content")
    assert record["output_size"] == len(b"pre-existing output content")
    assert record["source_hash"] == hashlib.sha256(b"original source content").hexdigest()
    assert record["crf"] is None

    captured = capsys.readouterr()
    assert f"Skipping {input_file} as the output file already exists." in captured.out

    # Run 2: Pre-existing file already in DB -> skips without re-inserting
    mock_tracker = MagicMock(wraps=MediaTracker(db_path))
    mock_tracker.__enter__.return_value = mock_tracker
    mock_tracker.get_record.return_value = record

    pipeline = MediaReducerPipeline(tracker=mock_tracker)
    batch_compress_directory(source_dir, output_dir, pipeline=pipeline)
    mock_tracker.save_record.assert_not_called()

    captured = capsys.readouterr()
    assert f"Skipping {input_file} as the output file already exists." in captured.out


def test_pipeline_constructor_di_skipped_records(tmp_path, capsys):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    db_path = tmp_path / "test.db"
    source_dir.mkdir(parents=True)

    input_file = source_dir / "item.mp4"
    content = b"content data"
    input_file.write_bytes(content)
    file_hash = hashlib.sha256(content).hexdigest()

    mock_compressor = MagicMock()
    mock_copier = MagicMock()

    # Test skipped_larger
    with MediaTracker(db_path) as tracker:
        tracker.save_record("item.mp4", file_hash, len(content), len(content) + 20, "skipped_larger", 23)
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=mock_compressor,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(source_dir, output_dir)
        mock_compressor.assert_not_called()
        mock_copier.assert_not_called()

    captured = capsys.readouterr()
    assert f"Skipping {input_file} as it was previously processed (status: skipped_larger)." in captured.out

    # Test compressed
    with MediaTracker(db_path) as tracker:
        tracker.save_record("item.mp4", file_hash, len(content), len(content) - 20, "compressed", 23)
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=mock_compressor,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(source_dir, output_dir)
        mock_compressor.assert_not_called()

    captured = capsys.readouterr()
    assert f"Skipping {input_file} as it was previously processed (status: compressed)." in captured.out

    # Test pre_existing
    with MediaTracker(db_path) as tracker:
        tracker.save_record("item.mp4", file_hash, len(content), len(content), "pre_existing", None)
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=mock_compressor,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(source_dir, output_dir)
        mock_compressor.assert_not_called()
        mock_copier.assert_not_called()

    captured = capsys.readouterr()
    assert f"Skipping {input_file} as it was previously processed (status: pre_existing)." in captured.out

    # Test skipped_crf
    with MediaTracker(db_path) as tracker:
        tracker.save_record("item.mp4", file_hash, len(content), None, "skipped_crf", 28)
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=mock_compressor,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(source_dir, output_dir)
        mock_compressor.assert_not_called()
        mock_copier.assert_not_called()

    captured = capsys.readouterr()
    assert f"Skipping {input_file} as it was previously processed (status: skipped_crf)." in captured.out


def test_pipeline_recompress_on_size_change(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    db_path = tmp_path / "test.db"

    source_dir.mkdir(parents=True)
    input_file = source_dir / "changed.mp4"
    input_file.write_bytes(b"new larger content here")

    with MediaTracker(db_path) as tracker:
        tracker.save_record(
            relative_path="changed.mp4",
            source_hash="old_hash",
            source_size=10,
            output_size=20,
            status="skipped_larger",
            crf=23,
        )

    def fake_compress(src, dest, crf):
        Path(dest).write_bytes(b"compressed")
        return True

    mock_copier = MagicMock()
    with MediaTracker(db_path) as tracker:
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=fake_compress,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(source_dir, output_dir)
        mock_copier.assert_called_once()


def test_pipeline_recompress_on_hash_change(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    db_path = tmp_path / "test.db"

    source_dir.mkdir(parents=True)
    input_file = source_dir / "same_size_diff_content.mp4"
    input_file.write_bytes(b"content_A")

    with MediaTracker(db_path) as tracker:
        tracker.save_record(
            relative_path="same_size_diff_content.mp4",
            source_hash="different_hash",
            source_size=9,
            output_size=15,
            status="skipped_larger",
            crf=23,
        )

    def fake_compress(src, dest, crf):
        Path(dest).write_bytes(b"comp")
        return True

    mock_copier = MagicMock()
    with MediaTracker(db_path) as tracker:
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=fake_compress,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(source_dir, output_dir)
        mock_copier.assert_called_once()


def test_pipeline_batch_compress_successful_larger_failed(tmp_path, capsys):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    db_path = tmp_path / "test.db"

    source_dir.mkdir(parents=True)

    file_ok = source_dir / "ok.mp4"
    file_ok.write_bytes(b"x" * 100)

    file_larger = source_dir / "larger.mp4"
    file_larger.write_bytes(b"x" * 50)

    file_fail = source_dir / "fail.mp4"
    file_fail.write_bytes(b"x" * 75)

    non_mp4 = source_dir / "ignore.txt"
    non_mp4.write_bytes(b"ignore me")

    def fake_compress(src, dest, crf):
        if "ok.mp4" in str(src):
            Path(dest).write_bytes(b"x" * 40)
            return True
        elif "larger.mp4" in str(src):
            Path(dest).write_bytes(b"x" * 80)
            return True
        return False

    mock_copier = MagicMock()

    with MediaTracker(db_path) as tracker:
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=fake_compress,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(source_dir, output_dir, target_crf=21)

        assert (output_dir / "ok.mp4").exists()
        assert not (output_dir / "larger.mp4").exists()
        assert not (output_dir / "fail.mp4").exists()

        rec_ok = tracker.get_record("ok.mp4")
        rec_larger = tracker.get_record("larger.mp4")
        rec_fail = tracker.get_record("fail.mp4")
        rec_txt = tracker.get_record("ignore.txt")

    assert rec_ok["status"] == "compressed"
    assert rec_ok["output_size"] == 40
    assert rec_ok["crf"] == 21

    assert rec_larger["status"] == "skipped_larger"
    assert rec_larger["output_size"] == 80
    assert rec_larger["crf"] == 21

    assert rec_fail["status"] == "failed"
    assert rec_fail["output_size"] is None
    assert rec_fail["crf"] == 21

    assert rec_txt is None

    captured = capsys.readouterr()
    assert f"Deleted {output_dir / 'larger.mp4'} as the output file is larger than the input file." in captured.out
    assert f"Failed to compress {file_fail}" in captured.out
    assert "Compression complete." in captured.out


def test_batch_compress_default_db_path(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    source_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    batch_compress_directory(source_dir, output_dir, db_path=None)
    assert (tmp_path / "media_reducer.db").exists()


def test_pipeline_skip_source_crf(tmp_path, capsys):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    db_path = tmp_path / "test.db"
    source_dir.mkdir(parents=True)

    input_file = source_dir / "hevc_crf28.mp4"
    content = b"hevc encoded video data"
    input_file.write_bytes(content)

    mock_compressor = MagicMock()
    mock_copier = MagicMock()
    mock_probe = MagicMock(return_value=("hevc", 28.0))

    with MediaTracker(db_path) as tracker:
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=mock_compressor,
            metadata_copier=mock_copier,
            probe_func=mock_probe,
        )
        pipeline.process_directory(source_dir, output_dir, target_crf=28)

        mock_probe.assert_called_once_with(input_file)
        mock_compressor.assert_not_called()
        mock_copier.assert_not_called()

        rec = tracker.get_record("hevc_crf28.mp4")
        assert rec is not None
        assert rec["status"] == "skipped_crf"
        assert rec["source_size"] == len(content)
        assert rec["output_size"] is None
        assert rec["crf"] == 28

    captured = capsys.readouterr()
    assert f"Skipping {input_file} as it is already compressed (hevc with CRF 28.0 >= threshold)." in captured.out


def test_pipeline_image_compression_and_filtering(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    db_path = tmp_path / "test.db"
    source_dir.mkdir(parents=True)

    img_jpg = source_dir / "photo.jpg"
    img_jpg.write_bytes(b"x" * 200)

    img_png = source_dir / "graphic.png"
    img_png.write_bytes(b"x" * 150)

    vid_mp4 = source_dir / "clip.mp4"
    vid_mp4.write_bytes(b"x" * 500)

    txt_file = source_dir / "notes.txt"
    txt_file.write_bytes(b"ignore me")

    def fake_video_compress(src, dest, crf):
        Path(dest).write_bytes(b"x" * 250)
        return True

    def fake_image_compress(src, dest, quality):
        Path(dest).write_bytes(b"x" * 100)
        return True

    mock_copier = MagicMock()

    # 1. Process all (both videos and images)
    with MediaTracker(db_path) as tracker:
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=fake_video_compress,
            image_compressor=fake_image_compress,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(
            source_dir,
            output_dir,
            target_crf=28,
            image_quality=4,
            include_videos=True,
            include_images=True,
        )

        assert (output_dir / "photo.jpg").exists()
        assert (output_dir / "graphic.png").exists()
        assert (output_dir / "clip.mp4").exists()
        assert not (output_dir / "notes.txt").exists()

        assert tracker.get_record("photo.jpg")["status"] == "compressed"
        assert tracker.get_record("graphic.png")["status"] == "compressed"
        assert tracker.get_record("clip.mp4")["status"] == "compressed"
        assert tracker.get_record("notes.txt") is None

    # 2. Filter: Only videos (include_images=False)
    dest_vids = tmp_path / "dest_vids"
    mock_img_compress = MagicMock()
    with MediaTracker(tmp_path / "test_vids.db") as tracker:
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=fake_video_compress,
            image_compressor=mock_img_compress,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(
            source_dir,
            dest_vids,
            include_videos=True,
            include_images=False,
        )
        assert (dest_vids / "clip.mp4").exists()
        assert not (dest_vids / "photo.jpg").exists()
        assert not (dest_vids / "graphic.png").exists()
        mock_img_compress.assert_not_called()

    # 3. Filter: Only images (include_videos=False)
    dest_imgs = tmp_path / "dest_imgs"
    mock_vid_compress = MagicMock()
    with MediaTracker(tmp_path / "test_imgs.db") as tracker:
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            compressor=mock_vid_compress,
            image_compressor=fake_image_compress,
            metadata_copier=mock_copier,
        )
        pipeline.process_directory(
            source_dir,
            dest_imgs,
            include_videos=False,
            include_images=True,
        )
        assert not (dest_imgs / "clip.mp4").exists()
        assert (dest_imgs / "photo.jpg").exists()
        assert (dest_imgs / "graphic.png").exists()
        mock_vid_compress.assert_not_called()


def test_pipeline_image_skipped_larger_and_failed(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    db_path = tmp_path / "test.db"
    source_dir.mkdir(parents=True)

    img_large = source_dir / "large.jpg"
    img_large.write_bytes(b"x" * 50)

    img_fail = source_dir / "fail.png"
    img_fail.write_bytes(b"x" * 50)

    def fake_image_compress(src, dest, quality):
        if "large.jpg" in str(src):
            Path(dest).write_bytes(b"x" * 100)  # Larger than input!
            return True
        return False

    with MediaTracker(db_path) as tracker:
        pipeline = MediaReducerPipeline(
            tracker=tracker,
            image_compressor=fake_image_compress,
        )
        pipeline.process_directory(source_dir, output_dir, image_quality=3)

        assert not (output_dir / "large.jpg").exists()
        assert not (output_dir / "fail.png").exists()

        rec_large = tracker.get_record("large.jpg")
        assert rec_large["status"] == "skipped_larger"
        assert rec_large["output_size"] == 100

        rec_fail = tracker.get_record("fail.png")
        assert rec_fail["status"] == "failed"
        assert rec_fail["output_size"] is None


def test_batch_compress_directory_with_custom_pipeline(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dest"
    source_dir.mkdir(parents=True)

    mock_pipeline = MagicMock()
    batch_compress_directory(
        source_dir,
        output_dir,
        target_crf=26,
        image_quality=5,
        include_videos=True,
        include_images=False,
        pipeline=mock_pipeline,
    )
    mock_pipeline.process_directory.assert_called_once_with(
        source_dir,
        output_dir,
        target_crf=26,
        image_quality=5,
        include_videos=True,
        include_images=False,
    )


def test_pipeline_compress_and_record_default_compress_fn(tmp_path):
    output_dir = tmp_path / "dest"
    output_dir.mkdir(parents=True)
    db_path = tmp_path / "test.db"

    input_file = tmp_path / "test.mp4"
    input_file.write_bytes(b"source content")
    out_file = output_dir / "test.mp4"

    def default_compress(src, dst, param):
        Path(dst).write_bytes(b"small")
        return True

    with MediaTracker(db_path) as tracker:
        pipeline = MediaReducerPipeline(tracker=tracker, compressor=default_compress)
        # Call _compress_and_record with compress_fn=None to test default branch
        pipeline._compress_and_record(input_file, out_file, "test.mp4", 28, len(b"source content"), None)
        rec = tracker.get_record("test.mp4")
        assert rec["status"] == "compressed"


