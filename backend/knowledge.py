# backend/knowledge.py — Baza de cunoștințe (Lookup Table) pentru probleme auto frecvente

from typing import Dict, List, Optional
import json
import os

# Calea către fișierul de "învățare" (feedback loop)
KNOWLEDGE_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.json")


def _load_user_reports() -> dict:
    """Încarcă raportările utilizatorilor (anonymizate) din JSON."""
    try:
        if os.path.exists(KNOWLEDGE_PATH):
            with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"reports": [], "model_scores": {}}


def _save_user_reports(data: dict) -> None:
    """Salvează raportările în JSON."""
    try:
        with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Knowledge] Eroare salvare: {e}")


class AutoExpertBrain:
    """
    Creierul expert auto — interoghează baza de cunoștințe bazată pe
    model + componentă (roți, motor, frâne etc.)
    """

    def __init__(self):
        # Lookup Table: probleme cunoscute per model (manualul de reparații + tendințe)
        self.common_faults: Dict[str, List[dict]] = {
            "skoda_fabia_6y": [
                {"component": "roți", "keywords": ["roți", "roat", "rulment", "suspens", "zgomot", "huruit", "vitez"], "faults": ["bucșe bară stabilizatoare", "rulmenți roată", "brațe oscilante"], "tip": "uzură prematură", "risc": 7},
                {"component": "frâne", "keywords": ["fran", "frin", "frana", "placute", "discuri"], "faults": ["plăcuțe uzate (min 3mm)", "discuri voalate", "lichid frână (schimb 2 ani)"], "tip": "uzură", "risc": 6},
                {"component": "abs", "keywords": ["abs", "senzor"], "faults": ["senzori ABS sensibili", "inel encoder murdar"], "tip": "eroare intermitentă", "risc": 5},
                {"component": "geam", "keywords": ["geam", "macara", "electric"], "faults": ["macara geam", "motor geam"], "tip": "defect electric", "risc": 4},
                {"component": "prag", "keywords": ["prag", "rugin"], "faults": ["rugină la praguri", "coroziune sub covorașe"], "tip": "coroziune", "risc": 8},
                {"component": "motor", "keywords": ["motor", "consum", "ulei", "apa", "pompa"], "faults": ["consum excesiv ulei (1.2 TSI)", "bucșe distributie"], "tip": "uzură motor", "risc": 6},
            ],
            "skoda_fabia": [
                {"component": "roți", "keywords": ["roți", "roat", "rulment", "suspens"], "faults": ["bucșe bară stabilizatoare", "rulmenți roată"], "tip": "uzură prematură", "risc": 7},
                {"component": "abs", "keywords": ["abs", "senzor"], "faults": ["senzori ABS sensibili"], "tip": "eroare intermitentă", "risc": 5},
            ],
            "vw_golf_7": [
                {"component": "motor", "keywords": ["motor", "apa", "pompa"], "faults": ["pompa de apă", "termostat"], "tip": "defect termic", "risc": 7},
                {"component": "infotainment", "keywords": ["ecran", "infotainment", "lag"], "faults": ["infotainment lag", "resetare MIB"], "tip": "software", "risc": 3},
            ],
            "dacia_logan": [
                {"component": "roți", "keywords": ["roți", "roat", "suspens"], "faults": ["bucșe brațe inferioare", "rulmenți"], "tip": "uzură", "risc": 6},
                {"component": "motor", "keywords": ["motor", "consum"], "faults": ["consum ulei (1.5 dCi)", "EGR"], "tip": "uzură", "risc": 5},
            ],
        }

    def _normalize_model(self, marca: str, model: str, series: str) -> str:
        """Returnează cheia de lookup (ex: skoda_fabia_6y)"""
        m = (marca or "").lower().replace(" ", "")
        mdl = (model or "").lower().replace(" ", "")
        s = (series or "").lower().replace(" ", "").replace("/", "")

        if "skoda" in m and ("fabia" in mdl or "fabia" in m):
            return f"skoda_fabia_{s}" if s else "skoda_fabia"
        if "vw" in m or "volkswagen" in m and "golf" in mdl:
            return "vw_golf_7"
        if "dacia" in m and "logan" in mdl:
            return "dacia_logan"
        # Fallback generic
        return f"{m}_{mdl}" if m and mdl else "skoda_fabia"

    def get_expert_advice(
        self,
        marca: str,
        model: str,
        series: str,
        component: str,
        user_message: str,
        include_preventive: bool = True,
    ) -> Optional[str]:
        """
        Caută în baza de cunoștințe problemele cunoscute pentru model + componentă.
        Returnează sfat expert + recomandare preventivă.
        """
        key = self._normalize_model(marca, model, series)
        entries = self.common_faults.get(key, self.common_faults.get("skoda_fabia", []))

        msg = (user_message or "").lower()
        def _norm(s):
            if not s: return ""
            return s.lower().replace("â", "a").replace("î", "i").replace("ț", "t").replace("ș", "s")
        comp_norm = _norm(component)
        for entry in entries:
            ent_comp = _norm(entry.get("component") or "")
            if any(kw in msg for kw in entry["keywords"]) and (not comp_norm or comp_norm in ent_comp):
                faults_str = ", ".join(entry["faults"])
                risk = entry.get("risc", 5)
                tip = entry.get("tip", "uzură")

                advice = f"""Probleme cunoscute la {marca or 'acest'} {model or ''} ({component}):

• {faults_str}

Tip: {tip} | Risc estimat: {risk}/10"""
                if include_preventive:
                    advice += """

Recomandare: Verifică la service și adaugă un reminder în Mulberry dacă e nevoie de interventie."""
                return advice

        return None

    def add_user_report(
        self,
        marca: str,
        model: str,
        component: str,
        fault_description: str,
    ) -> None:
        """
        Feedback loop — adaugă o raportare de la user (anonimizată).
        Dacă mai mulți raportează același lucru, crește scorul de risc.
        """
        data = _load_user_reports()
        reports = data.get("reports", [])

        key = self._normalize_model(marca, model, "")
        reports.append({
            "model_key": key,
            "component": component,
            "fault": fault_description,
            "count": 1,
        })

        # Agregare: numără câte raportări similare există
        model_scores = data.get("model_scores", {})
        comp_key = f"{key}_{component}"
        model_scores[comp_key] = model_scores.get(comp_key, 0) + 1

        data["reports"] = reports[-500:]  # păstrăm ultimele 500
        data["model_scores"] = model_scores
        _save_user_reports(data)

    def get_trending_risks(self, marca: str, model: str) -> List[tuple]:
        """
        Returnează componentele cu cel mai mare risc raportat de utilizatori.
        """
        data = _load_user_reports()
        model_scores = data.get("model_scores", {})
        key = self._normalize_model(marca, model, "")

        results = []
        for comp_key, count in model_scores.items():
            if comp_key.startswith(key + "_"):
                comp = comp_key.replace(key + "_", "")
                results.append((comp, count))
        results.sort(key=lambda x: -x[1])
        return results[:5]
