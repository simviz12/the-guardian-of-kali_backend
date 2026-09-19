"""Gemini AI Gateway adapter implementing AIGateway using Google Gemini API."""

import asyncio
import logging
import os
from typing import Any

import httpx

from src.application.dtos.responses import AIResponse
from src.application.ports.ai_gateway import AIGateway
from src.infrastructure.config.system_prompt import KALI_GUARDIAN_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

GEMINI_TOOL_DECLARATION: dict[str, Any] = {
    "function_declarations": [
        {
            "name": "propose_command",
            "description": "MANDATORY: Always call this function whenever the user asks for ANY hacking, reconnaissance, scanning, cracking, DNS, OSINT, or security command. Proposes the exact bash command ready to execute.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "command": {
                        "type": "STRING",
                        "description": "The exact bash command to execute inside Kali Linux (e.g. whois domain.com, dig domain.com ANY, theHarvester -d domain.com -b all, nmap, gobuster, etc.).",
                    },
                    "target": {
                        "type": "STRING",
                        "description": "The target host, IP, domain, or placeholder.",
                    },
                    "justification": {
                        "type": "STRING",
                        "description": "Explanation of what the command does and why.",
                    },
                },
                "required": ["command", "target", "justification"],
            },
        }
    ]
}


class GeminiAIGateway(AIGateway):
    """Adapter connecting to Google Gemini 2.5 Flash model supporting function calling
    and exponential backoff retry.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        system_prompt: str = KALI_GUARDIAN_SYSTEM_PROMPT,
        max_retries: int = 3,
    ) -> None:
        self._api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        )
        self._model = model
        self._system_prompt = system_prompt
        self._max_retries = max_retries

    async def send_message(
        self,
        prompt: str,
        history: list[dict[str, Any]],
    ) -> AIResponse:
        contents: list[dict[str, Any]] = []

        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": content}],
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}],
        })

        payload = {
            "contents": contents,
            "system_instruction": {
                "parts": [{"text": self._system_prompt}]
            },
            "tools": [GEMINI_TOOL_DECLARATION],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192,
            },
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"

        result_data = await self._call_with_retry(url, payload)

        text_content_parts: list[str] = []
        suggested_command: str | None = None
        tool_justification: str | None = None
        tool_target: str | None = None

        candidates = result_data.get("candidates", [])
        if candidates:
            first_candidate = candidates[0]
            parts = first_candidate.get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    text_content_parts.append(part["text"])
                if "functionCall" in part:
                    fn = part["functionCall"]
                    if fn.get("name") == "propose_command":
                        args = fn.get("args", {})
                        suggested_command = args.get("command")
                        tool_target = args.get("target")
                        tool_justification = args.get("justification")

        full_text = "\n\n".join(text_content_parts).strip()
        if not full_text and tool_justification:
            full_text = f"Proposed command for target '{tool_target}': {tool_justification}"
        elif not full_text and suggested_command:
            full_text = f"Proposed command: {suggested_command}"

        metadata = {
            "model": self._model,
            "provider": "google-gemini",
        }

        return AIResponse(
            content=full_text,
            suggested_command=suggested_command,
            metadata=metadata,
        )

    async def _call_with_retry(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        delay = 1.0
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    res = await client.post(url, json=payload)
                    res.raise_for_status()
                    return res.json()
                except Exception as exc:
                    if attempt == self._max_retries:
                        logger.error(f"Gemini API call failed after {attempt} attempts: {exc}")
                        raise
                    logger.warning(
                        f"Transient Gemini API error (attempt {attempt}/{self._max_retries}): {exc}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    delay *= 2.0
        return {}
