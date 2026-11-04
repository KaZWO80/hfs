"""Erzeugt eine Beispiel-Excel mit Testdaten (fiktive Person) in ../beispiele/.

Aufruf (im Ordner server/):  python beispiel_erstellen.py
"""

from datetime import datetime
from pathlib import Path

from excel_export import ZEITZONE, erstelle_excel
from models import Antwort

BEISPIEL = {
    "anrede": "Herr",
    "vorname": "Max",
    "nachname": "Mustermann",
    "anteil_ich_prozent": 50,
    "anteil_andere_prozent": 50,
    "gehindert_von": "2026-05-04",
    "gehindert_bis": "2026-07-31",
    "gehindert_grund": "Fraktur des rechten Handgelenks, 6 Wochen Gips, danach Physiotherapie.",
    "staffeln": [
        {"von": "2026-05-04", "bis": "2026-06-14", "prozent": 80},
        {"von": "2026-06-15", "bis": "2026-07-05", "prozent": 50},
        {"von": "2026-07-06", "bis": "2026-07-31", "prozent": 20},
    ],
    "schmerzen": "Schmerzen beim Greifen und Heben, beim Schlafen auf der rechten Seite, "
    "beim längeren Schreiben am PC.",
    "personen": 4,
    "kinder_alter": "6 und 11 Jahre",
    "wohnform": "Haus",
    "wohnverhaeltnis": "Eigentum",
    "wohnflaeche_qm": 140,
    "raeume": 5,
    "etagen": 2,
    "besonderheiten": "Steile Treppe ins Obergeschoss, Wäschekeller im Untergeschoss.",
    "garten": True,
    "garten_qm": 350,
    "geraete": ["mikrowelle", "staubsauger", "waschmaschine", "trockner", "spuelmaschine", "rasenmaeher"],
    "geraete_sonstiges": "Hochdruckreiniger",
    "haushaltshilfe_generell": False,
    "bezahlte_hilfe": True,
    "bezahlte_hilfe_von": "2026-05-11",
    "bezahlte_hilfe_bis": "2026-06-14",
    "bezahlte_hilfe_taetigkeiten": "Putzen und Wäsche, 2x wöchentlich je 3 Std.",
    "taetigkeiten_vor": {
        "staubsaugen": {"aktiv": True, "stunden_pro_woche": 1.5},
        "boden_wischen": {"aktiv": True, "stunden_pro_woche": 1},
        "fenster_putzen": {"aktiv": True, "stunden_pro_woche": 0.5},
        "bad_putzen": {"aktiv": True, "stunden_pro_woche": 1},
        "aufraeumen": {"aktiv": True, "stunden_pro_woche": 2},
        "geschirr_einraeumen": {"aktiv": True, "stunden_pro_woche": 1.5},
        "kochen": {"aktiv": True, "stunden_pro_woche": 5},
        "waesche_waschen": {"aktiv": True, "stunden_pro_woche": 2},
        "einkaufen": {"aktiv": True, "stunden_pro_woche": 3},
        "muell": {"aktiv": True, "stunden_pro_woche": 0.5},
        "autopflege": {"aktiv": True, "stunden_pro_woche": 0.5},
        "gartenpflege": {"aktiv": True, "stunden_pro_woche": 3, "detail": "Rasen mähen, Hecke schneiden"},
        "kinderbetreuung": {"aktiv": True, "stunden_pro_woche": 6, "detail": "Lena (6) und Tim (11)"},
    },
    "taetigkeiten_nach": {
        "staubsaugen": {"beeintraechtigt": True, "wieder_moeglich_ab": "2026-07-06"},
        "boden_wischen": {"beeintraechtigt": True, "wieder_moeglich_ab": "2026-07-06"},
        "fenster_putzen": {"beeintraechtigt": True},
        "bad_putzen": {"beeintraechtigt": True, "wieder_moeglich_ab": "2026-07-06"},
        "kochen": {"beeintraechtigt": True, "wieder_moeglich_ab": "2026-06-15"},
        "waesche_waschen": {"beeintraechtigt": True, "wieder_moeglich_ab": "2026-06-15"},
        "einkaufen": {"beeintraechtigt": True, "wieder_moeglich_ab": "2026-06-15"},
        "gartenpflege": {"beeintraechtigt": True, "wieder_moeglich_ab": "2026-08-01"},
    },
    "einwilligung": True,
    "aktenzeichen": "123/26",
}

if __name__ == "__main__":
    ziel = Path(__file__).resolve().parents[1] / "beispiele"
    pfad = erstelle_excel(Antwort(**BEISPIEL), ziel, datetime(2026, 11, 3, 14, 30, 0, tzinfo=ZEITZONE))
    print(pfad)
