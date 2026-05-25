"""
services/ai_service.py
----------------------
Wrapper around the Groq LLM API.

Centralizing the LLM client makes it easy to:
- swap models,
- tweak temperature,
- add retries / error handling,
- and reuse the same call signature everywhere.
"""

from typing import List, Dict, Optional

from groq import Groq

from config import Config
from utils.logger import get_logger


logger = get_logger("ai_service")


# Initialize the Groq client once at import time.
# If the API key is missing we still allow the app to boot — the route
# layer will surface a clean error when a call actually happens.
_groq_client: Optional[Groq] = None
if Config.GROQ_API_KEY:
    try:
        _groq_client = Groq(api_key=Config.GROQ_API_KEY)
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to initialize Groq client: %s", exc)
        _groq_client = None
else:
    logger.warning("GROQ_API_KEY is not set — AI responses will fall back to a default reply.")


def generate_response(
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    user_message: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 150,
) -> str:
    """
    Generate the next AI reply.

    Parameters
    ----------
    system_prompt : str
        Instructions describing the AI's persona/goal.
    chat_history : list[dict]
        Prior turns as [{"role": "user"|"assistant", "content": "..."}].
    user_message : str, optional
        The latest user utterance to append. If None, history is sent as-is.
    temperature : float
        LLM creativity (0.0 = deterministic, 1.0 = creative).
    max_tokens : int
        Hard cap on the reply length — we want short, phone-call style answers.

    Returns
    -------
    str
        The AI's spoken reply (already trimmed).
    """
    # Build the messages list expected by the Groq Chat Completions API.
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    if user_message:
        messages.append({"role": "user", "content": user_message})

    if _groq_client is None:
        logger.error("Groq client unavailable. Returning fallback reply.")
        return "I'm sorry, I'm having a little trouble right now. Could you say that again?"

    try:
        completion = _groq_client.chat.completions.create(
            model=Config.GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
        )
        reply = (completion.choices[0].message.content or "").strip()

        if not reply:
            return "Sorry, could you repeat that?"

        # Safety net: hard-trim very long answers so phone audio stays snappy.
        if len(reply) > 400:
            reply = reply[:400].rsplit(".", 1)[0] + "."

        return reply

    except Exception as exc:
        logger.exception("Groq API call failed: %s", exc)
        return "I'm sorry, I missed that. Could you say it one more time?"


def generate_call_summary(transcript_lines: List[str]) -> str:
    """
    Produce a 1-3 sentence summary of an entire call's transcript.
    Used to populate `Call.summary` after a call ends.
    """
    if not transcript_lines:
        return ""

    transcript_text = "\n".join(transcript_lines)
    system_prompt = (
        "You are an assistant that summarizes outbound sales call transcripts. "
        "Reply with 1 to 3 short sentences capturing: outcome, client interest, "
        "and any concrete next steps. Plain text only, no markdown."
    )

    return generate_response(
        system_prompt=system_prompt,
        chat_history=[],
        user_message=f"Summarize this call transcript:\n\n{transcript_text}",
        temperature=0.2,
        max_tokens=200,
    )
