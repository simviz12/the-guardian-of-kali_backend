"""Unit tests for the AI security assistant system prompt."""

from src.adapters.ai.claude_ai_gateway import ClaudeAIGateway
from src.infrastructure.config.system_prompt import KALI_GUARDIAN_SYSTEM_PROMPT


def test_system_prompt_contains_mandatory_ethical_and_scope_directives() -> None:
    """Verifies that the system prompt strictly establishes ethical scope, CTFs,
    explicit authorization, and refusal of destructive commands.
    """
    prompt = KALI_GUARDIAN_SYSTEM_PROMPT

    # 1. Identity & Ethical Learning Goal
    assert "The Guardian of Kali" in prompt
    assert "ethical hacking" in prompt
    assert "CTF" in prompt or "HackTheBox" in prompt

    # 2. Scope & Zero Assumed Authorization
    assert "EXPLICIT SCOPE" in prompt or "explicitly declared" in prompt
    assert "NEVER assume implicit authorization" in prompt
    assert "refuse" in prompt.lower()

    # 3. Tool-use and justification
    assert "propose_command" in prompt
    assert "reasoning" in prompt.lower() or "justification" in prompt.lower()

    # 4. Refusal of destructive commands
    assert "rm -rf" in prompt
    assert "destructive" in prompt.lower()


def test_claude_ai_gateway_defaults_to_kali_guardian_system_prompt() -> None:
    """Verifies that ClaudeAIGateway uses KALI_GUARDIAN_SYSTEM_PROMPT by default."""
    gateway = ClaudeAIGateway(api_key="test-key")
    assert gateway._system_prompt == KALI_GUARDIAN_SYSTEM_PROMPT
