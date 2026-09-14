import hashlib
from phone_media_reducer.utils import compute_file_hash


def test_compute_file_hash(tmp_path):
    test_file = tmp_path / "sample.txt"
    content = b"abcdefghijklmnopqrstuvwxyz0123456789"
    test_file.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    computed_hash = compute_file_hash(test_file, chunk_size=8)
    assert computed_hash == expected_hash
