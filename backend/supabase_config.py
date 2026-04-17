"""Config Supabase din variabile de mediu (URL + cheie anon/publishable)."""

from __future__ import annotations

import os
from typing import Tuple


def supabase_url() -> str:
    return (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")


def supabase_anon_key() -> str:
    return (os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY") or "").strip()


def supabase_config() -> Tuple[str, str]:
    return supabase_url(), supabase_anon_key()


def create_supabase_client():
    """Returnează clientul oficial dacă env-ul e setat și pachetul e instalat."""
    url, key = supabase_config()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL și SUPABASE_ANON_KEY (sau SUPABASE_KEY) trebuie setate.")
    from supabase import create_client

    return create_client(url, key)


def try_create_supabase_client():
    """None dacă lipsește config sau supabase nu e instalat."""
    url, key = supabase_config()
    if not url or not key:
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    return create_client(url, key)
