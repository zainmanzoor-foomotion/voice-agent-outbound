"""
services/prompt_service.py
--------------------------
Loads and renders the AI system prompt for a given client.

The prompt template lives in `prompts/sales_prompt.txt`. This service
substitutes business and client variables into the template so the
LLM always has the right context.
"""

from pathlib import Path
from typing import Optional

from config import Config
from models import Client


# Cache the file content in memory after the first read.
_PROMPT_TEMPLATE: Optional[str] = None


def _load_template() -> str:
    """Read the sales prompt file from disk (cached)."""
    global _PROMPT_TEMPLATE
    if _PROMPT_TEMPLATE is None:
        path = Path(__file__).resolve().parent.parent / "prompts" / "sales_prompt.txt"
        _PROMPT_TEMPLATE = path.read_text(encoding="utf-8")
    return _PROMPT_TEMPLATE


def build_system_prompt(client: Optional[Client] = None) -> str:
    """
    Build a system prompt string for the LLM, filling in business
    identity and (optionally) client-specific context.
    """
    template = _load_template()

    return template.format(
        agent_name=Config.AGENT_NAME,
        business_name=Config.BUSINESS_NAME,
        business_service=Config.BUSINESS_SERVICE,
        client_name=(client.name if client and client.name else "Unknown"),
        client_company=(client.company if client and client.company else "Unknown"),
    )


def build_initial_greeting(client: Optional[Client] = None) -> str:
    """
    Return the first line the AI agent speaks when the call connects.

    Kept short and warm. Personalized with the client's first name when available.
    """
    first_name = ""
    if client and client.name:
        first_name = client.name.split()[0]

    if first_name:
        return (
            f"Hi {first_name}, this is {Config.AGENT_NAME} calling from "
            f"{Config.BUSINESS_NAME}. Do you have a quick minute to chat?"
        )

    return (
        f"Hi there, this is {Config.AGENT_NAME} calling from "
        f"{Config.BUSINESS_NAME}. Do you have a quick minute to chat?"
    )
