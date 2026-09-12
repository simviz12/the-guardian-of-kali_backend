"""SQLite implementation of SessionRepository for persistent audit and history tracking."""

import asyncio
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any

from src.application.ports.session_repository import SessionRepository
from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.risk_level import RiskLevel

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT
);

CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    text TEXT NOT NULL,
    origin TEXT NOT NULL,
    target TEXT,
    risk_level TEXT,
    policy_decision TEXT,
    result TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS policy_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id INTEGER NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (command_id) REFERENCES commands (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_commands_session_id ON commands (session_id);
CREATE INDEX IF NOT EXISTS idx_commands_timestamp ON commands (timestamp);
CREATE INDEX IF NOT EXISTS idx_commands_risk_level ON commands (risk_level);
"""


class SQLiteSessionRepository(SessionRepository):
    """SQLite-backed session repository using standard library sqlite3 without any ORM.

    Attributes:
        _db_path (str): File system path to the SQLite database file or ':memory:'.
    """

    def __init__(self, db_path: str = "sessions.db") -> None:
        """Initializes the repository and provisions required tables.

        Args:
            db_path (str): Path to the SQLite database file. Defaults to 'sessions.db'.
        """
        self._db_path = db_path
        # If storing to file, ensure parent folder exists
        if self._db_path != ":memory:":
            parent_dir = os.path.dirname(self._db_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Creates and configures a new sqlite3 connection with foreign keys enabled."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """Executes the schema provisioning DDL statements."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)

    async def save(self, session: Session) -> None:
        """Persists the session and syncs its command history in an async thread.

        Args:
            session (Session): The session entity to save.
        """
        await asyncio.to_thread(self._save_sync, session)

    def _save_sync(self, session: Session) -> None:
        """Synchronous persistence logic executing inside worker thread."""
        session_id_str = str(session.id)
        start_str = session.started_at.isoformat()
        end_str = session.ended_at.isoformat() if session.ended_at else None

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Upsert session record
            cursor.execute(
                """
                INSERT INTO sessions (id, user, start, end)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user = excluded.user,
                    start = excluded.start,
                    end = excluded.end;
                """,
                (session_id_str, session.user, start_str, end_str),
            )

            # Insert commands not yet recorded
            for cmd in session.commands:
                cmd_timestamp_str = cmd.timestamp.isoformat()
                cmd_origin_str = cmd.origin.value
                risk_level_str = cmd.risk_level.value if cmd.risk_level else None

                # Check if this exact command for this session already exists
                cursor.execute(
                    """
                    SELECT id FROM commands
                    WHERE session_id = ? AND text = ? AND origin = ? AND timestamp = ?
                    LIMIT 1;
                    """,
                    (session_id_str, cmd.text, cmd_origin_str, cmd_timestamp_str),
                )
                existing = cursor.fetchone()

                if not existing:
                    cursor.execute(
                        """
                        INSERT INTO commands (
                            session_id, text, origin, target, risk_level,
                            policy_decision, result, timestamp
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            session_id_str,
                            cmd.text,
                            cmd_origin_str,
                            cmd.target,
                            risk_level_str,
                            risk_level_str,
                            None,
                            cmd_timestamp_str,
                        ),
                    )
                    inserted_cmd_id = cursor.lastrowid
                    if inserted_cmd_id:
                        cursor.execute(
                            """
                            INSERT INTO policy_logs (
                                command_id, decision, reason, timestamp
                            )
                            VALUES (?, ?, ?, ?);
                            """,
                            (
                                inserted_cmd_id,
                                risk_level_str or "PERMITTED",
                                f"Command {cmd_origin_str} evaluated with risk {risk_level_str or 'UNSPECIFIED'}",
                                cmd_timestamp_str,
                            ),
                        )

            conn.commit()

    async def get_history(self, filters: dict[str, Any]) -> list[Command]:
        """Queries executed commands filtered by user, session_id, date range, or risk_level.

        Args:
            filters (Dict[str, Any]): Filtering criteria. Supported keys:
                - 'session_id' (str or UUID): Filter by session identifier.
                - 'user' (str): Filter by session user.
                - 'start_date' (str or datetime): Start of date range (inclusive).
                - 'end_date' (str or datetime): End of date range (inclusive).
                - 'risk_level' (str or RiskLevel): Filter by risk level.

        Returns:
            List[Command]: Chronologically matched Command entities.
        """
        return await asyncio.to_thread(self._get_history_sync, filters)

    def _get_history_sync(self, filters: dict[str, Any]) -> list[Command]:
        """Synchronous query implementation executing inside worker thread."""
        query = """
            SELECT c.id, c.session_id, c.text, c.origin, c.target, c.risk_level,
                   c.policy_decision, c.result, c.timestamp
            FROM commands c
            JOIN sessions s ON c.session_id = s.id
            WHERE 1=1
        """
        params: list[Any] = []

        # Filter by session_id
        session_id = filters.get("session_id")
        if session_id is not None:
            query += " AND c.session_id = ?"
            params.append(str(session_id))

        # Filter by user
        user = filters.get("user")
        if user is not None:
            query += " AND s.user = ?"
            params.append(str(user))

        # Filter by date range
        start_date = filters.get("start_date")
        if start_date is not None:
            query += " AND c.timestamp >= ?"
            params.append(
                start_date.isoformat() if isinstance(start_date, datetime) else str(start_date)
            )

        end_date = filters.get("end_date")
        if end_date is not None:
            query += " AND c.timestamp <= ?"
            params.append(end_date.isoformat() if isinstance(end_date, datetime) else str(end_date))

        # Filter by risk_level
        risk_level = filters.get("risk_level")
        if risk_level is not None:
            risk_val = risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level)
            query += " AND c.risk_level = ?"
            params.append(risk_val)

        query += " ORDER BY c.timestamp ASC;"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            commands: list[Command] = []
            for row in rows:
                dt = datetime.fromisoformat(row["timestamp"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)

                risk = RiskLevel(row["risk_level"]) if row["risk_level"] else None
                origin = CommandOrigin(row["origin"])

                cmd = Command(
                    text=row["text"],
                    origin=origin,
                    target=row["target"],
                    timestamp=dt,
                    risk_level=risk,
                )
                commands.append(cmd)

            return commands
