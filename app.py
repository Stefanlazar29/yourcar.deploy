"""
app.py — Aplicație Streamlit YourCar.
Logica YourCar ID: dacă rca_expiry este NULL, afișează butonul de încărcare asigurare;
dacă asigurarea există, calculează și afișează scorul (ex: 89,67%).
"""
import sys
from decimal import Decimal
from typing import Optional

import streamlit as st

# Permite importul din backend când rulezi din rădăcina proiectului
sys.path.insert(0, ".")
from backend import database


def _format_score(value) -> str:
    """Formatează scorul cu virgulă ca separator zecimal (ex: 89,67%)."""
    if value is None:
        return "—"
    if isinstance(value, Decimal):
        value = float(value)
    return f"{value:.2f}".replace(".", ",") + "%"


def _compute_ycs_score(car) -> Optional[Decimal]:
    """
    Calculează YourCar Index Score. Dacă există ycs_score în DB, îl folosim;
    altfel, dacă asigurarea (rca_expiry) există, returnăm 89.67.
    """
    if getattr(car, "ycs_score", None) is not None:
        return Decimal(str(car.ycs_score))
    if getattr(car, "rca_expiry", None) is None:
        return None
    # Asigurare încărcată: afișăm scor exemplu 89,67%
    return Decimal("89.67")


def main():
    st.set_page_config(page_title="YourCar", layout="centered")
    st.title("YourCar")

    try:
        database.init_db()
        car = database.get_first_car()
    except Exception as e:
        st.warning(f"Baza de date nu e disponibilă: {e}. Verifică fișierul SQLite.")
        st.stop()

    if not car:
        st.info("Nu există încă niciun vehicul în baza de date. Adaugă unul din aplicația principală.")
        return

    # Secțiune YourCar ID
    st.subheader("YourCar ID")
    ycr = car.ycr_id or "—"
    st.write(f"**ID vehicul:** {ycr}")

    # Logica cerută: rca_expiry NULL → buton; altfel → scor 89,67%
    if car.rca_expiry is None:
        st.button(
            "Deblochează YourCar Index - Pasul 1: Încarcă Asigurarea",
            type="primary",
        )
        st.caption("După ce încarci asigurarea, vei putea vedea YourCar Index Score.")
    else:
        score = _compute_ycs_score(car)
        if score is not None:
            st.metric("YourCar Index Score", _format_score(score))
        else:
            st.write("Scor: —")


if __name__ == "__main__":
    main()
