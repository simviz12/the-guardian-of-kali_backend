"""Unit tests verifying the Session entity, its UUID assignment, and command ordering."""
from datetime import datetime, timezone, timedelta
from uuid import UUID

from src.domain.entities.command import Command
from src.domain.entities.session import Session
from src.domain.entities.target import Target
from src.domain.value_objects.command_origin import CommandOrigin
from src.domain.value_objects.risk_level import RiskLevel


def test_session_creation_defaults() -> None:
    """Verifies that a Session initializes with a valid UUID, timestamps, and empty lists."""
    session = Session(user="carlos")

    assert session.user == "carlos"
    assert isinstance(session.id, UUID)
    assert isinstance(session.started_at, datetime)
    assert session.ended_at is None
    assert len(session.commands) == 0
    assert len(session.authorized_targets) == 0


def test_session_unique_ids() -> None:
    """Verifies that distinct session instances receive distinct UUIDs."""
    s1 = Session(user="carlos")
    s2 = Session(user="carlos")

    assert s1.id != s2.id


def test_session_add_command_ordering() -> None:
    """Verifies that add_command keeps commands ordered by timestamp ascending."""
    session = Session(user="carlos")
    now = datetime.now(timezone.utc)

    cmd_older = Command(
        text="ping 127.0.0.1",
        origin=CommandOrigin.MANUAL_USER,
        timestamp=now - timedelta(minutes=5),
    )
    cmd_newer = Command(
        text="nmap 127.0.0.1",
        origin=CommandOrigin.AI,
        timestamp=now,
    )

    # Insert newer first, then older
    session.add_command(cmd_newer)
    session.add_command(cmd_older)

    # Must be ordered older -> newer
    assert session.commands[0].text == "ping 127.0.0.1"
    assert session.commands[1].text == "nmap 127.0.0.1"


def test_session_prevents_duplicate_commands() -> None:
    """Verifies that duplicate command entries are not inserted repeatedly."""
    session = Session(user="carlos")
    fixed_time = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    cmd1 = Command(text="whoami", origin=CommandOrigin.MANUAL_USER, timestamp=fixed_time)
    cmd1_duplicate = Command(text="whoami", origin=CommandOrigin.MANUAL_USER, timestamp=fixed_time)

    session.add_command(cmd1)
    session.add_command(cmd1_duplicate)

    assert len(session.commands) == 1


def test_session_end_session() -> None:
    """Verifies that end_session records a valid ended_at timestamp."""
    session = Session(user="carlos")
    assert session.ended_at is None

    session.end_session()
    assert isinstance(session.ended_at, datetime)
    assert session.ended_at >= session.started_at
