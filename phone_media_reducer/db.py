from pathlib import Path
import sqlite3
from typing import Optional, Union


class MediaTracker:
    """Manages SQLite persistence for tracking processed phone media."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> "MediaTracker":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def connect(self) -> None:
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self.init_schema()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def init_schema(self) -> None:
        assert self.conn is not None
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_files (
                    relative_path TEXT PRIMARY KEY,
                    source_hash TEXT,
                    source_size INTEGER,
                    output_size INTEGER,
                    status TEXT,
                    crf INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get_record(self, relative_path: str) -> Optional[sqlite3.Row]:
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM processed_files WHERE relative_path = ?", (relative_path,))
        return cursor.fetchone()

    def save_record(
        self,
        relative_path: str,
        source_hash: str,
        source_size: int,
        output_size: Optional[int],
        status: str,
        crf: Optional[int],
    ) -> None:
        assert self.conn is not None
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO processed_files (relative_path, source_hash, source_size, output_size, status, crf, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(relative_path) DO UPDATE SET
                    source_hash=excluded.source_hash,
                    source_size=excluded.source_size,
                    output_size=excluded.output_size,
                    status=excluded.status,
                    crf=excluded.crf,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (relative_path, source_hash, source_size, output_size, status, crf),
            )


def init_db(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Helper function to initialize a connection and create schema."""
    tracker = MediaTracker(db_path)
    tracker.connect()
    assert tracker.conn is not None
    return tracker.conn


def get_record(conn: sqlite3.Connection, relative_path: str) -> Optional[sqlite3.Row]:
    """Helper function to fetch record using raw connection."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM processed_files WHERE relative_path = ?", (relative_path,))
    return cursor.fetchone()


def save_record(
    conn: sqlite3.Connection,
    relative_path: str,
    source_hash: str,
    source_size: int,
    output_size: Optional[int],
    status: str,
    crf: Optional[int],
) -> None:
    """Helper function to save record using raw connection."""
    with conn:
        conn.execute(
            """
            INSERT INTO processed_files (relative_path, source_hash, source_size, output_size, status, crf, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(relative_path) DO UPDATE SET
                source_hash=excluded.source_hash,
                source_size=excluded.source_size,
                output_size=excluded.output_size,
                status=excluded.status,
                crf=excluded.crf,
                updated_at=CURRENT_TIMESTAMP
            """,
            (relative_path, source_hash, source_size, output_size, status, crf),
        )
