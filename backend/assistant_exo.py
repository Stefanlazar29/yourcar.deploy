"""
Mulberry EXO — apeluri rapide LLM (Groq prin AIProxy).

Folosește același flux ca exo_assistant, dar pentru prompturi scurte / diagnoză.
"""

from __future__ import annotations

import os

from backend import ai_proxy


def ask_exo_fast(prompt: str) -> str:
    """Răspuns rapid pentru analiză / rapoarte (Groq Llama 3 70B, fallback Ollama)."""
    p = (prompt or "").strip()
    if not p:
        return ""
    # Respectă modul local-only (date ultra-sensibile).
    task = "local_sensitive" if os.getenv("AI_USE_LOCAL_ONLY", "").strip().lower() in ("1", "true", "yes") else "fast_chat"
    return ai_proxy.complete_simple(p, task=task, max_completion_tokens=2048)
