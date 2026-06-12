"""
mulberry_analytics.py
Algoritmi Python pentru Mulberry Analytics Dashboard.

Structura:
  TransactionMetrics  — calcul % transfer / receive
  AnalyticsScore      — scor de creștere și donut SVG
  CashMetrics         — balanță + grafic bare
  FinancialDashboard  — agregă totul + endpoint FastAPI
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict


# ─── Modele de date ───────────────────────────────────────────

@dataclass
class TransactionMetrics:
    total: int
    transfer_count: int
    receive_count: int

    @property
    def transfer_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.transfer_count / self.total * 100, 1)

    @property
    def receive_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.receive_count / self.total * 100, 1)

    @property
    def transfer_users(self) -> int:
        return self.transfer_count

    @property
    def receive_users(self) -> int:
        return self.receive_count


@dataclass
class AnalyticsScore:
    current_value: float
    previous_value: float

    @property
    def growth_pct(self) -> float:
        if self.previous_value == 0:
            return 0.0
        raw = (self.current_value - self.previous_value) / self.previous_value * 100
        return round(raw, 1)

    @property
    def score(self) -> float:
        """Scor normalizat 0–100 bazat pe creștere."""
        return min(100.0, max(0.0, round(50 + self.growth_pct * 0.5, 1)))

    def donut_svg_params(self, radius: int = 46) -> Dict:
        """
        Calculează parametrii SVG stroke-dasharray pentru un donut chart.

        Formula:
          circumferinta = 2 * π * r
          filled        = circumferinta * (score / 100)
          gap           = circumferinta - filled

        Returnează dict cu 'stroke_dasharray' gata de injectat în SVG.
        """
        circ = 2 * math.pi * radius
        filled = circ * (self.score / 100)
        gap = circ - filled
        return {
            "radius": radius,
            "circumference": round(circ, 2),
            "filled": round(filled, 2),
            "gap": round(gap, 2),
            "stroke_dasharray": f"{filled:.1f} {gap:.1f}",
            "score_pct": self.score,
        }


@dataclass
class CashMetrics:
    current_balance: float
    balance_prev_week: float

    @property
    def growth_pct(self) -> float:
        if self.balance_prev_week == 0:
            return 0.0
        return round(
            (self.current_balance - self.balance_prev_week) / self.balance_prev_week * 100,
            1,
        )

    def bar_chart_heights(self, n_bars: int = 4) -> List[float]:
        """
        Generează înălțimi normalizate (0.0–1.0) pentru barele graficului.
        Ultima bară este mereu 1.0 (valoarea curentă = maxim).

        Algoritmul: decădere exponențială inversă — simulează o tendință
        de creștere pe ultimele n săptămâni.
        """
        heights = []
        for i in range(n_bars):
            # i=0 → cea mai veche, i=n_bars-1 → curentă
            t = i / (n_bars - 1)          # 0.0 ... 1.0
            h = t ** 1.8                   # creștere accelerată spre final
            heights.append(round(h, 3))
        return heights


@dataclass
class PaymentTransaction:
    name: str
    amount: float
    currency: str = "RON"

    def formatted_amount(self) -> str:
        return f"{self.amount:,.0f} {self.currency}"


# ─── Dashboard principal ───────────────────────────────────────

@dataclass
class FinancialDashboard:
    # Balanță header
    balance: float = 1_655.00
    income: float = 950.00
    expenses: float = 382.00

    # Tranzacții
    transactions: TransactionMetrics = field(default_factory=lambda: TransactionMetrics(
        total=37,
        transfer_count=24,   # ≈ 65 %
        receive_count=11,    # ≈ 31 %
    ))

    # Analytics
    analytics: AnalyticsScore = field(default_factory=lambda: AnalyticsScore(
        current_value=178_500,
        previous_value=100_000,
    ))

    # Cash
    cash: CashMetrics = field(default_factory=lambda: CashMetrics(
        current_balance=816_752,
        balance_prev_week=606_000,
    ))

    # Period
    authorized_users: int = 18_785
    period_months: int = 3

    # Payments
    payments: List[PaymentTransaction] = field(default_factory=lambda: [
        PaymentTransaction("Repayment cash", 1_120),
        PaymentTransaction("Office leasing", 3_810),
        PaymentTransaction("Employee salary", 12_760),
    ])

    def summary(self) -> Dict:
        """Returnează dict complet pentru a alimenta frontend-ul."""
        return {
            "header": {
                "balance": self.balance,
                "income": self.income,
                "expenses": self.expenses,
            },
            "transfer": {
                "pct": self.transactions.transfer_pct,
                "users": self.transactions.transfer_users,
            },
            "receive": {
                "pct": self.transactions.receive_pct,
                "users": self.transactions.receive_users,
            },
            "analytics": {
                "growth_pct": self.analytics.growth_pct,
                "score_pct": self.analytics.score,
                "donut": self.analytics.donut_svg_params(radius=46),
            },
            "cash": {
                "balance": self.cash.current_balance,
                "growth_pct": self.cash.growth_pct,
                "bar_heights": self.cash.bar_chart_heights(n_bars=4),
            },
            "period": {
                "authorized_users": self.authorized_users,
                "months": self.period_months,
            },
            "payments": [
                {"name": p.name, "amount": p.amount, "formatted": p.formatted_amount()}
                for p in self.payments
            ],
        }


# ─── FastAPI router (adaugă în main.py) ───────────────────────
#
# from fastapi import APIRouter
# from mulberry_analytics import FinancialDashboard
#
# router = APIRouter()
# _dashboard = FinancialDashboard()
#
# @router.get("/api/analytics-dashboard")
# def get_analytics_dashboard():
#     return _dashboard.summary()
#
# @router.get("/api/analytics-dashboard/donut")
# def get_donut_params(radius: int = 46):
#     return _dashboard.analytics.donut_svg_params(radius=radius)


# ─── CLI demo ─────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    d = FinancialDashboard()
    print(json.dumps(d.summary(), indent=2, ensure_ascii=False))
