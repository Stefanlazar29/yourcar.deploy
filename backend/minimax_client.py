"""
Compatibilitate: vechile apeluri MiniMax sunt rutate prin AIProxy (Groq + fallback Ollama).

Pentru chei MiniMax legacy, setează MINIMAX_FORCE=1 — altfel se folosește Groq.
"""

import os
from typing import List, Optional

from backend import ai_proxy

# Re-export pentru cod care importă constante
MINIMAX_URL = "https://api.minimax.io/v1/text/chatcompletion_v2"
DEFAULT_MODEL = "M2-her"
SYSTEM_BASE = ai_proxy.SYSTEM_BASE


def _use_legacy_minimax() -> bool:
    return os.getenv("MINIMAX_FORCE", "").strip().lower() in ("1", "true", "yes")


def _minimax_raw_call(
    user_message: str,
    extra_context: Optional[str] = None,
    *,
    system_override: Optional[str] = None,
    messages_with_system: Optional[List[dict]] = None,
) -> str:
    """Apel direct MiniMax (doar dacă MINIMAX_FORCE=1)."""
    import requests

    api_key = (os.getenv("MINIMAX_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY lipsește (MINIMAX_FORCE activ).")

    system = (system_override.strip() if system_override else SYSTEM_BASE)
    if extra_context and extra_context.strip():
        label = "CONTEXT vehicul" if system_override else "Context intern (folosește doar dacă e relevant)"
        system += f"\n\n--- {label} ---\n" + extra_context.strip()[:8000]

    if messages_with_system is not None:
        body = {
            "model": os.getenv("MINIMAX_MODEL", DEFAULT_MODEL),
            "messages": [{"role": "system", "content": system}] + list(messages_with_system),
            "max_completion_tokens": 1500,
            "temperature": 0.4,
        }
    else:
        body = {
            "model": os.getenv("MINIMAX_MODEL", DEFAULT_MODEL),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message.strip()},
            ],
            "max_completion_tokens": 1024,
            "temperature": 0.35 if system_override else 0.7,
        }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.post(MINIMAX_URL, json=body, headers=headers, timeout=120)
    r.raise_for_status()
    data = r.json()
    base = data.get("base_resp") or {}
    if base.get("status_code") not in (None, 0):
        msg = base.get("status_msg") or "Eroare MiniMax"
        raise RuntimeError(f"MiniMax: {msg} (code={base.get('status_code')})")
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("MiniMax: răspuns fără choices")
    msg = choices[0].get("message") or {}
    content = (msg.get("content") or "").strip()
    if not content:
        raise RuntimeError("MiniMax: conținut gol")
    return content


def call_minimax(
    user_message: str,
    extra_context: Optional[str] = None,
    *,
    system_override: Optional[str] = None,
) -> str:
    if _use_legacy_minimax():
        return _minimax_raw_call(user_message, extra_context, system_override=system_override)
    task = "local_sensitive" if os.getenv("AI_USE_LOCAL_ONLY", "").strip().lower() in ("1", "true", "yes") else "fast_chat"
    if system_override and "JSON" in system_override[:80]:
        task = "json_structured"
    return ai_proxy.complete_simple(
        user_message,
        extra_context,
        system_override=system_override,
        task=task,
        max_completion_tokens=1024,
    )


def call_minimax_with_history(
    system: str,
    messages: List[dict],
    *,
    max_completion_tokens: int = 1500,
    temperature: float = 0.4,
) -> str:
    if _use_legacy_minimax():
        return _minimax_raw_call("", None, system_override=system, messages_with_system=messages)
    return ai_proxy.complete_with_history(
        system,
        messages,
        task="fast_chat",
        max_completion_tokens=max_completion_tokens,
        temperature=temperature,
    )


def exo_chat_short(msg: str) -> str:
    """Opțional pentru arhive — delegă la rapid."""
    from backend.assistant_exo import ask_exo_fast

    return ask_exo_fast(msg)
