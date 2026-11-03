import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel

from app.domain import Problem, canonical_hash


class Store:
    """Local-only store; each mutation holds a short, explicit SQLite transaction."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    kind TEXT NOT NULL,
                    id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    PRIMARY KEY (kind, id)
                );
                CREATE TABLE IF NOT EXISTS requests (
                    scope TEXT NOT NULL,
                    key TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    PRIMARY KEY (scope, key)
                );
                CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY,
                    at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    action TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    content_hash TEXT
                );
                """
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def get(connection: sqlite3.Connection, kind: str, record_id: str) -> str:
        row = connection.execute(
            "SELECT body FROM records WHERE kind = ? AND id = ?", (kind, record_id)
        ).fetchone()
        if row is None:
            raise Problem(404, "not_found", "Record not found")
        return str(row[0])

    @staticmethod
    def put(connection: sqlite3.Connection, kind: str, record_id: str, body: BaseModel) -> None:
        connection.execute(
            "INSERT INTO records(kind,id,body) VALUES (?,?,?) "
            "ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body",
            (kind, record_id, body.model_dump_json()),
        )

    @staticmethod
    def replay(
        connection: sqlite3.Connection, scope: str, key: str, payload: BaseModel
    ) -> str | None:
        row = connection.execute(
            "SELECT payload_hash, record_id FROM requests WHERE scope=? AND key=?", (scope, key)
        ).fetchone()
        if row is None:
            return None
        if row[0] != canonical_hash(payload):
            raise Problem(
                409, "idempotency_conflict", "Key was already used with a different payload"
            )
        return str(row[1])

    @staticmethod
    def reserve(
        connection: sqlite3.Connection, scope: str, key: str, payload: BaseModel, record_id: str
    ) -> None:
        connection.execute(
            "INSERT INTO requests VALUES (?,?,?,?)",
            (scope, key, canonical_hash(payload), record_id),
        )

    @staticmethod
    def audit(
        connection: sqlite3.Connection, action: str, record_id: str, content_hash: str | None = None
    ) -> None:
        connection.execute(
            "INSERT INTO audit(action,record_id,content_hash) VALUES (?,?,?)",
            (action, record_id, content_hash),
        )

    def events(self) -> list[dict[str, object]]:
        with self.transaction() as connection:
            connection.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT sequence,at,action,record_id,content_hash FROM audit ORDER BY sequence"
                )
            ]

    def fail_interrupted_runs(self) -> None:
        with self.transaction() as connection:
            for record_id, body in connection.execute(
                "SELECT id,body FROM records WHERE kind='presentation'"
            ).fetchall():
                data = json.loads(body)
                if data["state"] == "generating":
                    data.update(state="failed", error_code="interrupted_generation")
                    connection.execute(
                        "UPDATE records SET body=? WHERE kind='presentation' AND id=?",
                        (json.dumps(data), record_id),
                    )
                    self.audit(connection, "generation_interrupted", record_id)
