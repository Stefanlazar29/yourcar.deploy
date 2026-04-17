"""
YourCar — aplicație Streamlit (legacy / dev local).
Fost app.py din rădăcină: redenumit ca Railway Nixpacks să nu trateze Streamlit ca intrare principală.

Rulare locală: pip install streamlit && streamlit run yourcar_streamlit_app.py
"""
import sys
from decimal import Decimal
from typing import Optional

import streamlit as st

sys.path.insert(0, ".")
from backend import database


def _format_score(value) -> str:
  if value is None:
    return "—"
  if isinstance(value, Decimal):
    value = float(value)
  return f"{value:.2f}".replace(".", ",") + "%"


def _compute_ycs_score(car) -> Optional[Decimal]:
  if getattr(car, "ycs_score", None) is not None:
    return Decimal(str(car.ycs_score))
  if getattr(car, "rca_expiry", None) is None:
    return None
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

  st.subheader("YourCar ID")
  ycr = car.ycr_id or "—"
  st.write(f"**ID vehicul:** {ycr}")

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
