"""Unit tests for SQLiteSessionRepository."""

from datetime import UTC, datetime, timedelta

import pytest

from src.adapters.storage.sqlite_session_repository import SQLiteSessionRepository
from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.risk_level import RiskLevel


@pytest.fixture
def repo(tmp_path) -> SQLiteSessionRepository:
    """Fixture providing a clean SQLite session repository with an isolated temp database."""
    db_file = str(tmp_path / "test_sessions.db")
    return SQLiteSessionRepository(db_path=db_file)


def test_tables_created(repo: SQLiteSessionRepository) -> None:
    """Verifies that sessions, commands, and policy_logs tables are provisioned."""
    conn = repo._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall()]
    assert "sessions" in tables
    assert "commands" in tables
    assert "policy_logs" in tables
    conn.close()


@pytest.mark.asyncio
async def test_save_and_retrieve_session(repo: SQLiteSessionRepository) -> None:
    """Verifies saving a session and retrieving command history without filters."""
    session = Session(user="carlos")
    cmd1 = Command(text="whoami", origin=CommandOrigin.MANUAL_USER, risk_level=RiskLevel.LOW)
    cmd2 = Command(text="ping -c 1 127.0.0.1", origin=CommandOrigin.AI, risk_level=RiskLevel.LOW)
    session.add_command(cmd1)
    session.add_command(cmd2)

    await repo.save(session)

    history = await repo.get_history({"session_id": session.id})
    assert len(history) == 2
    assert history[0].text == "whoami"
    assert history[0].origin == CommandOrigin.MANUAL_USER
    assert history[1].text == "ping -c 1 127.0.0.1"
    assert history[1].origin == CommandOrigin.AI

    # Verify audit entries in policy_logs
    conn = repo._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT command_id, decision, reason FROM policy_logs;")
    policy_rows = cursor.fetchall()
    assert len(policy_rows) == 2
    assert policy_rows[0]["decision"] == "LOW"
    conn.close()


@pytest.mark.asyncio
async def test_filter_by_user(repo: SQLiteSessionRepository) -> None:
    """Verifies filtering command history by session user."""
    s1 = Session(user="carlos")
    s1.add_command(Command(text="ls -la", origin=CommandOrigin.MANUAL_USER))
    await repo.save(s1)

    s2 = Session(user="ia-user")
    s2.add_command(Command(text="nmap 10.10.10.1", origin=CommandOrigin.AI))
    await repo.save(s2)

    carlos_history = await repo.get_history({"user": "carlos"})
    assert len(carlos_history) == 1
    assert carlos_history[0].text == "ls -la"

    ia_history = await repo.get_history({"user": "ia-user"})
    assert len(ia_history) == 1
    assert ia_history[0].text == "nmap 10.10.10.1"


@pytest.mark.asyncio
async def test_filter_by_risk_level(repo: SQLiteSessionRepository) -> None:
    """Verifies filtering command history by evaluated risk_level."""
    session = Session(user="carlos")
    cmd_low = Command(text="whoami", origin=CommandOrigin.AI, risk_level=RiskLevel.LOW)
    cmd_high = Command(
        text="hydra -l admin -P pass.txt 10.10.10.1",
        origin=CommandOrigin.AI,
        risk_level=RiskLevel.HIGH,
    )
    cmd_blocked = Command(text="rm -rf /", origin=CommandOrigin.AI, risk_level=RiskLevel.BLOCKED)

    session.add_command(cmd_low)
    session.add_command(cmd_high)
    session.add_command(cmd_blocked)
    await repo.save(session)

    high_history = await repo.get_history({"risk_level": RiskLevel.HIGH})
    assert len(high_history) == 1
    assert high_history[0].text == "hydra -l admin -P pass.txt 10.10.10.1"

    blocked_history = await repo.get_history({"risk_level": "BLOCKED"})
    assert len(blocked_history) == 1
    assert blocked_history[0].text == "rm -rf /"


@pytest.mark.asyncio
async def test_filter_by_date_range(repo: SQLiteSessionRepository) -> None:
    """Verifies filtering command history by start_date and end_date."""
    now = datetime.now(UTC)
    old_time = now - timedelta(days=2)
    future_time = now + timedelta(days=2)

    session = Session(user="carlos")
    cmd_past = Command(text="old command", origin=CommandOrigin.MANUAL_USER, timestamp=old_time)
    cmd_current = Command(text="current command", origin=CommandOrigin.MANUAL_USER, timestamp=now)
    cmd_future = Command(
        text="future command", origin=CommandOrigin.MANUAL_USER, timestamp=future_time
    )

    session.add_command(cmd_past)
    session.add_command(cmd_current)
    session.add_command(cmd_future)
    await repo.save(session)

    # Filter commands between yesterday and tomorrow
    start_filter = now - timedelta(days=1)
    end_filter = now + timedelta(days=1)

    filtered = await repo.get_history({"start_date": start_filter, "end_date": end_filter})
    assert len(filtered) == 1
    assert filtered[0].text == "current command"


@pytest.mark.asyncio
async def test_session_update_ended_at(repo: SQLiteSessionRepository) -> None:
    """Verifies updating a session with ended_at persists cleanly."""
    session = Session(user="carlos")
    await repo.save(session)

    session.end_session()
    await repo.save(session)

    conn = repo._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT start, end FROM sessions WHERE id = ?", (str(session.id),))
    row = cursor.fetchone()
    assert row["start"] is not None
    assert row["end"] is not None
    conn.close()
