from phone_media_reducer.db import MediaTracker, get_record, init_db, save_record


def test_media_tracker_lifecycle_and_crud(tmp_path):
    db_path = tmp_path / "tracker_test.db"

    # Using context manager
    with MediaTracker(db_path) as tracker:
        assert tracker.get_record("videos/1.mp4") is None

        tracker.save_record(
            relative_path="videos/1.mp4",
            source_hash="hash1",
            source_size=1000,
            output_size=500,
            status="compressed",
            crf=23,
        )

        record = tracker.get_record("videos/1.mp4")
        assert record is not None
        assert record["relative_path"] == "videos/1.mp4"
        assert record["source_hash"] == "hash1"
        assert record["source_size"] == 1000
        assert record["output_size"] == 500
        assert record["status"] == "compressed"
        assert record["crf"] == 23

        # Test UPSERT (update existing record)
        tracker.save_record(
            relative_path="videos/1.mp4",
            source_hash="hash2",
            source_size=1200,
            output_size=600,
            status="compressed",
            crf=20,
        )

        updated = tracker.get_record("videos/1.mp4")
        assert updated["source_hash"] == "hash2"
        assert updated["source_size"] == 1200
        assert updated["output_size"] == 600
        assert updated["crf"] == 20

        # Call connect again while already connected (idempotency check)
        tracker.connect()

    # Ensure connection is closed after context exit
    assert tracker.conn is None
    # Calling close again when None is safe
    tracker.close()


def test_db_helper_functions(tmp_path):
    db_path = tmp_path / "helpers_test.db"
    conn = init_db(db_path)

    try:
        assert get_record(conn, "videos/2.mp4") is None

        save_record(
            conn,
            relative_path="videos/2.mp4",
            source_hash="hash_a",
            source_size=2000,
            output_size=1000,
            status="compressed",
            crf=22,
        )

        record = get_record(conn, "videos/2.mp4")
        assert record is not None
        assert record["relative_path"] == "videos/2.mp4"
        assert record["source_hash"] == "hash_a"
        assert record["source_size"] == 2000
        assert record["output_size"] == 1000
        assert record["status"] == "compressed"
        assert record["crf"] == 22

        # Test UPSERT with helper
        save_record(
            conn,
            relative_path="videos/2.mp4",
            source_hash="hash_b",
            source_size=2100,
            output_size=1100,
            status="skipped_larger",
            crf=24,
        )

        updated = get_record(conn, "videos/2.mp4")
        assert updated["source_hash"] == "hash_b"
        assert updated["source_size"] == 2100
        assert updated["output_size"] == 1100
        assert updated["status"] == "skipped_larger"
        assert updated["crf"] == 24
    finally:
        conn.close()
