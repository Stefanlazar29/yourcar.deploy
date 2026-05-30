"""
Mulberry Desktop — PyQt6 companion UI.
OLED black / neon yellow (#E1FF00) design, 14 px border radius.
Connects to the Mulberry server (default http://46.225.100.151:8080).

Run:  python -m backend.ui
"""
from __future__ import annotations

import sys
import time
from typing import Optional

import urllib.request
import urllib.error
from PyQt6.QtCore import (
    Qt, QObject, QThread, QTimer, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget,
)

# ── Design tokens ─────────────────────────────────────────────────────────────
BG       = "#080808"
SURF     = "#111111"
SURF2    = "#181818"
NEON     = "#E1FF00"
NEON_H   = "#EEFF66"
NEON_P   = "#C8E000"
NEON_DIM = "rgba(225,255,0,0.13)"
BORDER   = "rgba(225,255,0,0.13)"
TEXT     = "#FFFFFF"
DIM      = "#888888"
GREEN    = "#22C55E"
RED      = "#FF4444"
R        = 14          # border-radius px
API_BASE = "http://46.225.100.151:8080"

QSS = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "DM Sans", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
    border: none;
}}

/* ── Sidebar ── */
#sidebar {{
    background-color: {SURF};
    border-right: 1px solid {BORDER};
}}
#sidebar QPushButton {{
    background: transparent;
    color: {DIM};
    border-radius: {R}px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}}
#sidebar QPushButton:hover {{
    background: rgba(225,255,0,0.08);
    color: {NEON};
}}
#sidebar QPushButton[active="true"] {{
    background: rgba(225,255,0,0.13);
    color: {NEON};
}}

/* ── Cards ── */
#card {{
    background-color: {SURF};
    border: 1px solid {BORDER};
    border-radius: {R}px;
}}

/* ── Neon button ── */
#neonBtn {{
    background-color: {NEON};
    color: #000000;
    border-radius: {R}px;
    padding: 10px 24px;
    font-size: 13px;
    font-weight: 700;
}}
#neonBtn:hover  {{ background-color: {NEON_H}; }}
#neonBtn:pressed {{ background-color: {NEON_P}; }}

/* ── Ghost button ── */
#ghostBtn {{
    background: transparent;
    color: {DIM};
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: {R}px;
    padding: 10px 24px;
    font-size: 13px;
}}
#ghostBtn:hover {{
    border-color: rgba(225,255,0,0.35);
    color: {NEON};
}}

/* ── Input ── */
QLineEdit {{
    background-color: {SURF2};
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: {R}px;
    padding: 10px 14px;
    color: {TEXT};
    font-size: 13px;
    selection-background-color: rgba(225,255,0,0.25);
}}
QLineEdit:focus {{
    border-color: rgba(225,255,0,0.50);
}}

/* ── Scroll bar ── */
QScrollBar:vertical {{
    background: transparent;
    width: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(225,255,0,0.25);
    border-radius: 2px;
    min-height: 40px;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{ height: 0; }}

/* ── H-line separator ── */
#hline {{
    background: {BORDER};
    max-height: 1px;
    border: none;
}}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def lbl(
    text: str,
    *,
    size: int = 13,
    bold: bool = False,
    dim: bool = False,
    neon: bool = False,
    selectable: bool = False,
) -> QLabel:
    w = QLabel(text)
    w.setWordWrap(True)
    parts = [f"font-size:{size}px"]
    if bold:
        parts.append("font-weight:700")
    if dim:
        parts.append(f"color:{DIM}")
    elif neon:
        parts.append(f"color:{NEON}")
    w.setStyleSheet(";".join(parts))
    if selectable:
        w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return w


class Card(QWidget):
    """Rounded surface card."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(20, 20, 20, 20)
        self._vbox.setSpacing(10)

    def add(self, w: QWidget) -> None:
        self._vbox.addWidget(w)

    def add_layout(self, layout) -> None:
        self._vbox.addLayout(layout)


def hline() -> QWidget:
    line = QWidget()
    line.setObjectName("hline")
    line.setFixedHeight(1)
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return line


# ── Health-check worker (runs in QThread) ─────────────────────────────────────

class HealthWorker(QObject):
    done = pyqtSignal(bool, float)

    def __init__(self, base: str) -> None:
        super().__init__()
        self._base = base

    @pyqtSlot()
    def run(self) -> None:
        import json as _json
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(f"{self._base}/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                ok = resp.status == 200 and _json.loads(resp.read()).get("ok") is True
        except Exception:
            ok = False
        self.done.emit(ok, (time.monotonic() - t0) * 1000)


# ── Dashboard page ────────────────────────────────────────────────────────────

class DashboardPage(QWidget):
    def __init__(self, api_base: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._base = api_base
        self._thread: Optional[QThread] = None
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._ping)
        self._timer.start(5000)
        self._ping()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        root.addWidget(lbl("Dashboard", size=22, bold=True))
        root.addWidget(lbl("Server status & live metrics", dim=True))

        # ── Status card ──
        status_card = Card()

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{DIM};font-size:20px")
        top_row.addWidget(self._dot)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._status_lbl = lbl("Checking…", size=15, bold=True)
        self._latency_lbl = lbl("—", dim=True)
        text_col.addWidget(self._status_lbl)
        text_col.addWidget(self._latency_lbl)
        top_row.addLayout(text_col)
        top_row.addStretch()

        self._url_lbl = lbl(self._base, dim=True, selectable=True)
        top_row.addWidget(self._url_lbl)

        status_card.add_layout(top_row)
        status_card.add(hline())
        self._detail_lbl = lbl("Waiting for first ping…", dim=True)
        status_card.add(self._detail_lbl)

        root.addWidget(status_card)

        # ── Info row ──
        info_row = QHBoxLayout()
        info_row.setSpacing(16)

        ep_card = Card()
        ep_card.add(lbl("Active endpoint", dim=True))
        ep_card.add(lbl("/health", size=15, bold=True, neon=True))
        ep_card.add(lbl("GET · JSON · public", dim=True))
        info_row.addWidget(ep_card)

        db_card = Card()
        db_card.add(lbl("Database", dim=True))
        db_card.add(lbl("SQLite", size=15, bold=True))
        db_card.add(lbl("SQLITE_PATH env · /data/mulberry.db (Docker)", dim=True))
        info_row.addWidget(db_card)

        root.addLayout(info_row)
        root.addStretch()

    def _ping(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        self._thread = QThread()
        worker = HealthWorker(self._base)
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.done.connect(self._on_done)
        worker.done.connect(lambda *_: self._thread.quit())
        self._thread.start()

    @pyqtSlot(bool, float)
    def _on_done(self, ok: bool, ms: float) -> None:
        if ok:
            self._dot.setStyleSheet(f"color:{GREEN};font-size:20px")
            self._status_lbl.setText("Online")
            self._status_lbl.setStyleSheet(f"font-size:15px;font-weight:700;color:{GREEN}")
            self._latency_lbl.setText(f"{ms:.0f} ms")
            self._detail_lbl.setText(
                f"GET {self._base}/health → 200 OK  ·  {ms:.0f} ms"
            )
        else:
            self._dot.setStyleSheet(f"color:{RED};font-size:20px")
            self._status_lbl.setText("Offline")
            self._status_lbl.setStyleSheet(f"font-size:15px;font-weight:700;color:{RED}")
            self._latency_lbl.setText("—")
            self._detail_lbl.setText(
                f"Cannot reach {self._base}/health — is uvicorn running?"
            )


# ── Vehicles page ─────────────────────────────────────────────────────────────

class VehiclesPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        root.addWidget(lbl("Vehicle Registry", size=22, bold=True))
        root.addWidget(lbl("Cars stored in the local SQLite database", dim=True))

        card = Card()
        card.add(lbl("First registered vehicle", dim=True))
        card.add(hline())

        try:
            from backend.database import get_first_car, init_db
            init_db()
            car = get_first_car()
        except Exception as exc:
            car = None
            card.add(lbl(f"DB error: {exc}", dim=True))

        if car:
            for field, val in [
                ("YCR ID",     car.ycr_id),
                ("RCA Expiry", car.rca_expiry),
                ("YCS Score",  car.ycs_score),
            ]:
                row = QHBoxLayout()
                k = lbl(field, dim=True)
                k.setFixedWidth(120)
                v = lbl(str(val) if val is not None else "—", bold=True)
                row.addWidget(k)
                row.addWidget(v)
                row.addStretch()
                w = QWidget()
                w.setLayout(row)
                card.add(w)
        else:
            card.add(lbl("No vehicles registered yet.", dim=True))

        root.addWidget(card)
        root.addStretch()


# ── Settings page ─────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    server_changed = pyqtSignal(str)

    def __init__(self, api_base: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build(api_base)

    def _build(self, api_base: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        root.addWidget(lbl("Settings", size=22, bold=True))

        card = Card()
        card.add(lbl("API Server URL", dim=True))
        self._url_input = QLineEdit(api_base)
        self._url_input.setPlaceholderText("http://46.225.100.151:8080")
        card.add(self._url_input)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("neonBtn")
        apply_btn.setFixedWidth(120)
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)
        btn_row.addStretch()
        w = QWidget()
        w.setLayout(btn_row)
        card.add(w)

        root.addWidget(card)
        root.addStretch()

    def _apply(self) -> None:
        url = self._url_input.text().strip().rstrip("/")
        if url:
            self.server_changed.emit(url)


# ── Sidebar ───────────────────────────────────────────────────────────────────

_NAV = [("Dashboard", 0), ("Vehicles", 1), ("Settings", 2)]


class Sidebar(QWidget):
    page_requested = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(200)
        self._btns: list[QPushButton] = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 24, 12, 24)
        layout.setSpacing(4)

        logo = QLabel("Mul<span style='color:#E1FF00'>berry</span>")
        logo.setTextFormat(Qt.TextFormat.RichText)
        logo.setStyleSheet(
            "font-size:20px;font-weight:800;padding:8px 8px 28px 8px;"
            f"background:transparent;"
        )
        layout.addWidget(logo)

        for name, idx in _NAV:
            btn = QPushButton(name)
            btn.setProperty("active", "false")
            btn.clicked.connect(lambda _, i=idx: self.select(i))
            self._btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        ver = QLabel("v0.1.0")
        ver.setStyleSheet(f"color:{DIM};font-size:11px;padding:4px 8px;background:transparent")
        layout.addWidget(ver)

        self.select(0)

    def select(self, idx: int) -> None:
        for i, btn in enumerate(self._btns):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.page_requested.emit(idx)


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Mulberry Desktop")
        self.resize(1020, 680)
        self._base = API_BASE
        self._build()

    def _build(self) -> None:
        root_w = QWidget()
        self.setCentralWidget(root_w)
        hbox = QHBoxLayout(root_w)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_requested.connect(self._switch)
        hbox.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._dashboard = DashboardPage(self._base)
        self._vehicles  = VehiclesPage()
        self._settings  = SettingsPage(self._base)
        self._settings.server_changed.connect(self._on_server_change)

        for w in (self._dashboard, self._vehicles, self._settings):
            self._stack.addWidget(w)

        hbox.addWidget(self._stack)

    def _switch(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

    def _on_server_change(self, url: str) -> None:
        self._base = url
        old = self._dashboard
        self._dashboard = DashboardPage(url)
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.insertWidget(0, self._dashboard)
        self._stack.setCurrentIndex(0)
        self._sidebar.select(0)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
