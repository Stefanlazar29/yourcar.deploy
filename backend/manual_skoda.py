"""
Protocol „gândire” pentru manualul local Skoda Fabia 6Y (sample).
Pasul A: încarcă fișierul text din resources/.
Pasul B: extrage pasaje relevante după cuvinte-cheie (linii 1-indexed).
Pasul C: text introductiv pentru răspunsuri personalizate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Relativ la rădăcina proiectului (folder părinte al backend/)
ROOT = Path(__file__).resolve().parent.parent
MANUAL_PATH = ROOT / "resources" / "skoda_fabia_6y_manual_sample.txt"


@dataclass
class ManualAnalysis:
    """Rezultat Pas A+B."""

    excerpts: List[Dict[str, Any]] = field(default_factory=list)
    """[{line_from, line_to, text}, ...]"""
    alert: Optional[Dict[str, str]] = None
    """{kind, title, detail} pentru Digital Twin UI."""
    matched_line_numbers: List[int] = field(default_factory=list)


def _load_lines() -> List[Tuple[int, str]]:
    if not MANUAL_PATH.is_file():
        return []
    raw = MANUAL_PATH.read_text(encoding="utf-8", errors="replace")
    out: List[Tuple[int, str]] = []
    for i, line in enumerate(raw.splitlines(), start=1):
        out.append((i, line.rstrip("\n\r")))
    return out


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("ă", "a").replace("â", "a").replace("î", "i")
    s = s.replace("ș", "s").replace("ț", "t")
    return s


# (tuple of keyword substrings in normalized message, line numbers 1-based inclusive)
_TOPIC_RANGES: List[Tuple[Tuple[str, ...], Tuple[int, int]]] = [
    (("cloc", "stabiliz", "bara", "denivel"), (7, 7)),  # bucșe bară — „cloc cloc”
    (("abs", "senzor", "encoder"), (9, 9)),
    (("ulei", "consum", "tsi", "0.5", "0,5"), (13, 13)),
    (("volant", "bimasa", "ambreiaj", "ambreja"), (3, 3)),
    (("rulment", "huruit", "viraj", "vitez"), (4, 4)),
    (("prag", "rugina", "rugine", "corozi"), (11, 11)),
    (("infotainment", "ecran", "motor 1.0", "1.2 tsi", "pornire", "vibrat"), (3, 3)),  # volantă / pornire
]


def analyze_user_message(message: str) -> ManualAnalysis:
    """
    Pasul A: citește manualul.
    Pasul B: potrivește întrebarea cu segmente (linii).
    """
    lines = _load_lines()
    if not lines:
        return ManualAnalysis()

    q = _norm(message)
    hit_ranges: Set[Tuple[int, int]] = set()
    for keywords, span in _TOPIC_RANGES:
        if any(k in q for k in keywords):
            hit_ranges.add(span)

    # potrivire slabă: orice mențiune skoda/fabia/6y
    if not hit_ranges and any(x in q for x in ("skoda", "fabia", "6y")):
        hit_ranges.add((1, 2))

    if not hit_ranges:
        return ManualAnalysis()

    excerpts: List[Dict[str, Any]] = []
    seen_lines: Set[int] = set()
    alert: Optional[Dict[str, str]] = None

    for lo, hi in sorted(hit_ranges):
        chunk: List[str] = []
        for ln, text in lines:
            if lo <= ln <= hi and ln not in seen_lines:
                seen_lines.add(ln)
                chunk.append(text)
        if not chunk:
            continue
        body = "\n".join(chunk).strip()
        if body:
            excerpts.append({"line_from": lo, "line_to": hi, "text": body})

    matched = sorted(seen_lines)

    # Alertă vizuală: ABS sau consum ulei
    if any(9 in range(r[0], r[1] + 1) for r in hit_ranges) or ("abs" in q or "senzor" in q):
        alert = {
            "kind": "abs_sensors",
            "title": "Sistem ABS / senzori",
            "detail": "Manualul Fabia 6Y: erori intermitente pot veni de la inel encoder murdar sau conexiuni. Verifică la service.",
        }
    elif any(13 in range(r[0], r[1] + 1) for r in hit_ranges) or ("ulei" in q and "consum" in q):
        alert = {
            "kind": "oil_consumption",
            "title": "Consum ulei (1.2 TSI)",
            "detail": "Manualul menționează consum crescut la unele motoare CBZA/CBZB — verifică nivelul lunar.",
        }

    return ManualAnalysis(excerpts=excerpts, alert=alert, matched_line_numbers=matched)


def merge_into_reply(reply_core: str, analysis: ManualAnalysis) -> str:
    """Pasul C: prefix din manual + răspunsul asistentului."""
    if not analysis.excerpts:
        return reply_core
    parts = [
        "📘 **Informație din manualul Skoda Fabia 6Y** (extras pentru mașina ta):\n",
    ]
    for ex in analysis.excerpts:
        lf, lt = ex["line_from"], ex["line_to"]
        parts.append(f"*Liniile {lf}" + (f"–{lt}" if lf != lt else "") + "*\n")
        parts.append(f"> {ex['text']}\n")
    parts.append("\n---\n\n")
    parts.append(reply_core)
    return "".join(parts)
