"""
AIProxy — chat: Gemini (Google AI) sau Groq; local: Ollama.

Variabile:
  GEMINI_API_KEY sau GOOGLE_API_KEY — Gemini pentru MulberryEXO (fast_chat).
  AI_CHAT_PROVIDER=gemini|groq — implicit: gemini dacă există GEMINI_API_KEY, altfel Groq.
  GEMINI_MODEL — ex. gemini-2.0-flash, gemini-1.5-flash
  GROQ_API_KEY — Groq (fallback chat + task-uri json_structured, etc.).
  GROQ_MODEL_FAST — default: llama-3.1-8b-instant
  MULBERRY_EXO_MOCK=1 — răspuns fix fără LLM (test UI)
  OLLAMA_BASE_URL / OLLAMA_MODEL — fallback local
  AI_USE_LOCAL_ONLY=1 — doar Ollama
  AI_SKIP_GROQ=1 — fără Groq (Gemini rămâne pentru chat dacă e setat)
  AI_DEBUG_LATENCY=1 — stdout: model, backend și durata fiecărui apel LLM + mesaje FALLBACK între furnizori
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Literal, Optional

import httpx

# Ultimul backend folosit pentru complete_chat (pentru persist /me chat).
_LAST_CHAT_BACKEND: Optional[str] = None

TaskKind = Literal[
    "fast_chat",
    "json_structured",
    "classify",
    "archive_summary",
    "local_sensitive",
]

SYSTEM_BASE = (
    "Ești MulberryExoTerra — mod analitic tehnic (România). "
    "Răspuns în română, dens, fără politețe de umplutură: fără saluturi gen „Bună”, „Cu plăcere”, „Desigur”, fără fraze de închidere inutile. "
    "Începe direct cu conținutul util. Structură: titluri scurte + liste bullet când clarifică. "
    "Prioritizează contextul intern furnizat; nu inventa date; dacă lipsește informația, spui explicit „necunoscut în context”. "
    "Nu pretinde acces internet live. Ton inginer/auto, nu customer support."
)


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def _ai_debug_latency() -> bool:
    """Log latență + fallback-uri (print pe stdout, util pentru dev / smoke)."""
    return _env_bool("AI_DEBUG_LATENCY") or _env_bool("AI_DEBUG")


def _latency_debug(backend: str, model_id: str, elapsed_sec: float) -> None:
    if not _ai_debug_latency():
        return
    print("--- AI DEBUG ---", flush=True)
    print(f"Backend: {backend}", flush=True)
    print(f"Model: {model_id}", flush=True)
    print(f"Timp răspuns: {round(elapsed_sec, 2)} secunde", flush=True)


def _fallback_debug(message: str) -> None:
    if not _ai_debug_latency():
        return
    print(f"FALLBACK: {message}", flush=True)


_DEFAULT_GROQ = "llama-3.1-8b-instant"


def _groq_model_for_task(task: TaskKind) -> str:
    if task in ("json_structured", "classify"):
        return os.getenv("GROQ_MODEL_STRUCTURED", os.getenv("GROQ_MODEL_FAST", _DEFAULT_GROQ))
    return os.getenv("GROQ_MODEL_FAST", _DEFAULT_GROQ)


def _temperature_for_task(task: TaskKind) -> float:
    if task in ("json_structured", "classify"):
        return 0.2
    if task == "archive_summary":
        return 0.35
    return 0.55


def _maybe_mock_exo_response() -> Optional[str]:
    """UI/dev: fără apel LLM când MULBERRY_EXO_MOCK=1."""
    if not _env_bool("MULBERRY_EXO_MOCK"):
        return None
    custom = (os.getenv("MULBERRY_EXO_MOCK_TEXT") or "").strip()
    if custom:
        return custom
    return (
        "[MOCK MulberryEXO] Răspuns fix pentru test (scroll/design). "
        "Setează MULBERRY_EXO_MOCK=0 pentru Gemini/Groq real."
    )


def get_last_chat_backend() -> str:
    """După ultimul complete_chat: gemini | groq | ollama | mock."""
    return _LAST_CHAT_BACKEND or "groq"


def _gemini_api_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def _use_gemini_for_chat() -> bool:
    """Chat MulberryEXO (fast_chat): Gemini dacă e cheie + provider nu forțează Groq."""
    if not _gemini_api_key():
        return False
    prov = (os.getenv("AI_CHAT_PROVIDER") or "").strip().lower()
    if prov == "groq":
        return False
    if prov == "gemini":
        return True
    # Implicit: preferă Gemini când există cheie (altfel rămâne Groq dacă nu e GEMINI_API_KEY)
    return True


def _gemini_model() -> str:
    return (os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip() or "gemini-2.0-flash"


def _call_gemini(
    system: str,
    messages: List[Dict[str, str]],
    *,
    task: TaskKind,
    max_completion_tokens: int,
) -> str:
    """Google Gemini generateContent (REST v1beta), format chat user/model."""
    api_key = _gemini_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY (sau GOOGLE_API_KEY) lipsește.")

    contents: List[Dict[str, Any]] = []
    for m in messages:
        role = (m.get("role") or "user").lower()
        if role == "assistant":
            role = "model"
        if role not in ("user", "model"):
            role = "user"
        content = (m.get("content") or "").strip()
        if not content:
            continue
        contents.append({"role": role, "parts": [{"text": content}]})

    if not contents:
        raise RuntimeError("Gemini: niciun mesaj user.")

    body: Dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": (system or "").strip()}]},
        "contents": contents,
        "generationConfig": {
            "temperature": _temperature_for_task(task),
            "maxOutputTokens": max_completion_tokens,
        },
    }

    model = _gemini_model()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    used_model = model
    t0 = time.perf_counter()
    try:
        r = httpx.post(url, json=body, timeout=120.0)
        if r.status_code == 404 and model != "gemini-1.5-flash":
            url_fb = (
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
                f"?key={api_key}"
            )
            used_model = "gemini-1.5-flash"
            r = httpx.post(url_fb, json=body, timeout=120.0)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        err_txt = ""
        try:
            err_txt = (e.response.text or "")[:500]
        except Exception:
            pass
        raise RuntimeError(f"Gemini HTTP {e.response.status_code}: {err_txt or e}") from e
    except Exception as e:
        raise RuntimeError(f"Gemini: {e}") from e

    cands = data.get("candidates") or []
    if not cands:
        fb = data.get("promptFeedback") or {}
        raise RuntimeError(f"Gemini: fără candidates (promptFeedback={fb})")
    parts = (cands[0].get("content") or {}).get("parts") or []
    texts: List[str] = []
    for p in parts:
        if isinstance(p, dict) and p.get("text"):
            texts.append(str(p["text"]))
    text = "".join(texts).strip()
    if not text:
        raise RuntimeError("Gemini: răspuns gol")
    _latency_debug("gemini", used_model, time.perf_counter() - t0)
    return text


def _ollama_url() -> str:
    return (os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL") or "llama3"


def _groq_messages_to_openai(
    system: str,
    messages: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = [{"role": "system", "content": system.strip()}]
    for m in messages:
        role = (m.get("role") or "user").lower()
        if role not in ("user", "assistant"):
            role = "user"
        content = (m.get("content") or "").strip()
        if content:
            out.append({"role": role, "content": content})
    return out


def _call_groq(
    system: str,
    messages: List[Dict[str, str]],
    *,
    task: TaskKind,
    max_completion_tokens: int,
) -> str:
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY lipsește. Adaugă cheia în backend/.env.")
    try:
        from groq import Groq
    except ImportError as e:
        raise RuntimeError("Pachetul 'groq' nu e instalat. Rulează: pip install groq") from e

    client = Groq(api_key=api_key)
    model = _groq_model_for_task(task)
    msgs = _groq_messages_to_openai(system, messages)
    t0 = time.perf_counter()
    chat = client.chat.completions.create(
        model=model,
        messages=msgs,
        max_tokens=max_completion_tokens,
        temperature=_temperature_for_task(task),
    )
    choice = chat.choices[0].message
    content = (getattr(choice, "content", None) or "").strip()
    if not content:
        raise RuntimeError("Groq: răspuns gol")
    resolved = str(getattr(chat, "model", None) or model)
    _latency_debug("groq", resolved, time.perf_counter() - t0)
    return content


def _call_ollama(
    system: str,
    messages: List[Dict[str, str]],
    *,
    task: TaskKind,
    max_completion_tokens: int,
) -> str:
    url = f"{_ollama_url()}/api/chat"
    o_msgs: List[Dict[str, str]] = [{"role": "system", "content": system.strip()}]
    for m in messages:
        role = (m.get("role") or "user").lower()
        if role not in ("user", "assistant"):
            role = "user"
        content = (m.get("content") or "").strip()
        if content:
            o_msgs.append({"role": role, "content": content})
    om = _ollama_model()
    body = {
        "model": om,
        "messages": o_msgs,
        "stream": False,
        "options": {
            "temperature": _temperature_for_task(task),
            "num_predict": max_completion_tokens,
        },
    }
    t0 = time.perf_counter()
    try:
        r = httpx.post(url, json=body, timeout=180.0)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"Ollama: {e}") from e
    msg = (data.get("message") or {}).get("content") or ""
    content = (msg or "").strip()
    if not content:
        raise RuntimeError("Ollama: răspuns gol")
    _latency_debug("ollama", om, time.perf_counter() - t0)
    return content


def complete_chat(
    system: str,
    messages: List[Dict[str, str]],
    *,
    task: TaskKind = "fast_chat",
    max_completion_tokens: int = 1500,
) -> str:
    """
    Chat (fast_chat): Gemini dacă GEMINI_API_KEY și AI_CHAT_PROVIDER nu forțează Groq; la eșec → Groq → Ollama.
    Alte task-uri: Groq; la eșec → Gemini (dacă există cheie) → Ollama.
    """
    global _LAST_CHAT_BACKEND

    mock = _maybe_mock_exo_response()
    if mock is not None:
        _LAST_CHAT_BACKEND = "mock"
        return mock

    system = (system or "").strip()
    if not system:
        raise RuntimeError("AIProxy: system prompt gol.")

    use_local = task == "local_sensitive" or _env_bool("AI_USE_LOCAL_ONLY")
    skip_groq = _env_bool("AI_SKIP_GROQ")

    if use_local:
        _LAST_CHAT_BACKEND = "ollama"
        return _call_ollama(system, messages, task=task, max_completion_tokens=max_completion_tokens)

    if task == "fast_chat" and _use_gemini_for_chat():
        try:
            _LAST_CHAT_BACKEND = "gemini"
            return _call_gemini(system, messages, task=task, max_completion_tokens=max_completion_tokens)
        except Exception as gem_err:
            if not skip_groq:
                _fallback_debug(f"Gemini a eșuat ({str(gem_err)[:160]}), pornesc Groq")
                try:
                    _LAST_CHAT_BACKEND = "groq"
                    return _call_groq(system, messages, task=task, max_completion_tokens=max_completion_tokens)
                except Exception as groq_inner:
                    _fallback_debug(f"Groq a eșuat ({str(groq_inner)[:160]}), pornesc Ollama")
            else:
                _fallback_debug(f"Gemini a eșuat ({str(gem_err)[:160]}), pornesc Ollama (AI_SKIP_GROQ)")
            try:
                _LAST_CHAT_BACKEND = "ollama"
                return _call_ollama(system, messages, task=task, max_completion_tokens=max_completion_tokens)
            except Exception as oe:
                raise RuntimeError(f"Gemini: {gem_err}; fallback eșuat: {oe}") from gem_err

    if skip_groq:
        _LAST_CHAT_BACKEND = "ollama"
        return _call_ollama(system, messages, task=task, max_completion_tokens=max_completion_tokens)

    try:
        _LAST_CHAT_BACKEND = "groq"
        return _call_groq(system, messages, task=task, max_completion_tokens=max_completion_tokens)
    except Exception as groq_err:
        if _gemini_api_key() and not skip_groq:
            _fallback_debug(f"Groq a eșuat ({str(groq_err)[:160]}), pornesc Gemini")
            try:
                _LAST_CHAT_BACKEND = "gemini"
                return _call_gemini(system, messages, task=task, max_completion_tokens=max_completion_tokens)
            except Exception as gem_err:
                _fallback_debug(f"Gemini a eșuat ({str(gem_err)[:160]}), pornesc Ollama")
                try:
                    _LAST_CHAT_BACKEND = "ollama"
                    return _call_ollama(system, messages, task=task, max_completion_tokens=max_completion_tokens)
                except Exception as ollama_err:
                    raise RuntimeError(f"Groq: {groq_err}; Gemini: {gem_err}; Ollama: {ollama_err}") from groq_err
        _fallback_debug(f"Groq a eșuat ({str(groq_err)[:160]}), pornesc Ollama")
        try:
            _LAST_CHAT_BACKEND = "ollama"
            return _call_ollama(system, messages, task=task, max_completion_tokens=max_completion_tokens)
        except Exception as ollama_err:
            raise RuntimeError(f"Groq: {groq_err}; Ollama fallback: {ollama_err}") from ollama_err


def complete_simple(
    user_message: str,
    extra_context: Optional[str] = None,
    *,
    system_override: Optional[str] = None,
    task: TaskKind = "fast_chat",
    max_completion_tokens: int = 1024,
) -> str:
    """Un singur turn user (compatibil cu vechiul call_minimax)."""
    system = (system_override.strip() if system_override else SYSTEM_BASE)
    if extra_context and extra_context.strip():
        label = "CONTEXT vehicul" if system_override else "Context intern"
        system += f"\n\n--- {label} ---\n" + extra_context.strip()[:8000]
    messages: List[Dict[str, str]] = [{"role": "user", "content": (user_message or "").strip()}]
    return complete_chat(system, messages, task=task, max_completion_tokens=max_completion_tokens)


def complete_with_history(
    system: str,
    messages: List[dict],
    *,
    task: TaskKind = "fast_chat",
    max_completion_tokens: int = 1500,
    temperature: Optional[float] = None,
) -> str:
    """Istoric user/assistant (fără system în `messages`). Parametrul temperature e ignorat (folosim task routing)."""
    _ = temperature
    norm: List[Dict[str, str]] = []
    for h in messages:
        role = (h.get("role") or "user").lower()
        if role not in ("user", "assistant"):
            role = "user"
        content = (h.get("content") or h.get("text") or "").strip()
        if content:
            norm.append({"role": role, "content": content})
    return complete_chat(system, norm, task=task, max_completion_tokens=max_completion_tokens)


def archive_executive_summary(payload: Dict[str, Any], *, max_chars: int = 3500) -> str:
    """Raport stil Executive Summary / BIOS (scurt, dens) din snapshot JSON."""
    hint = json.dumps(payload, ensure_ascii=False)[:max_chars]
    system = (
        "Ești analist BI auto pentru flota Mulberry. Generează un rezumat executiv stil BIOS/POST: "
        "secțiuni scurte cu etichete [OK]/[WARN]/[CRIT], fără proză lungă. Română. "
        "Maxim 12 linii, bullet-uri. Fără markdown excesiv."
    )
    user = "Date snapshot (JSON):\n" + hint
    return complete_simple(user, task="archive_summary", system_override=system, max_completion_tokens=900)
