import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from excel_export import TEMPLATE, ZEITZONE, Korrektur, dateiname_teil, erstelle_excel  # noqa: E402
from models import Antwort  # noqa: E402
from questionnaire import GERAETE, TAETIGKEITEN  # noqa: E402

ZEIT = datetime(2026, 11, 3, 14, 5, 9, tzinfo=ZEITZONE)


def beispiel(**extra) -> dict:
    d = {
        "nachname": "Müller-Lüdenscheidt",
        "vorname": "Jörg",
        "anrede": "Herr",
        "anteil_ich_prozent": 60,
        "anteil_andere_prozent": 40,
        "gehindert_von": "2026-01-10",
        "gehindert_bis": "2026-03-10",
        "gehindert_grund": "Armbruch rechts",
        "staffeln": [
            {"von": "2026-01-10", "bis": "2026-01-31", "prozent": 100},
            {"von": "2026-02-01", "bis": "2026-03-10", "prozent": 50},
        ],
        "personen": 3,
        "wohnform": "Haus",
        "wohnverhaeltnis": "Eigentum",
        "garten": True,
        "garten_qm": 200,
        "geraete": ["mikrowelle", "spuelmaschine"],
        "taetigkeiten_vor": {
            "kochen": {"aktiv": True, "stunden_pro_woche": 7},
            "staubsaugen": {"aktiv": True, "stunden_pro_woche": 1.5},
            "waesche_waschen": {"aktiv": True, "stunden_pro_woche": 2},
            "gartenpflege": {"aktiv": True, "stunden_pro_woche": 3, "detail": "Rasen mähen"},
        },
        "taetigkeiten_nach": {"kochen": {"beeintraechtigt": True, "wieder_moeglich_ab": "2026-02-15"}},
        "einwilligung": True,
        "installations_id": "test-1234-abcd",
    }
    d.update(extra)
    return d


def texte(ws) -> list:
    return [c.value for r in ws.iter_rows() for c in r if c.value is not None]


@pytest.fixture
def datei(tmp_path):
    return erstelle_excel(Antwort(**beispiel()), tmp_path, ZEIT)


# ------------------------------------------------------------- Dateiname --

def test_dateiname_teil():
    assert dateiname_teil("Müller-Lüdenscheidt") == "Mueller-Luedenscheidt"
    assert dateiname_teil("Weiß") == "Weiss"
    assert dateiname_teil(" Jean Paul / ../x ") == "Jean-Paul-x"
    assert dateiname_teil("Ñúñez") == "Nunez"
    assert dateiname_teil("///") == "unbekannt"


def test_dateiname(datei):
    assert datei.name == "HFS_Mueller-Luedenscheidt_Joerg_2026-11-03_140509.xlsx"


def test_gleicher_name_gleiche_zeit_ueberschreibt_nicht(tmp_path):
    a = Antwort(**beispiel())
    p1 = erstelle_excel(a, tmp_path, ZEIT)
    p2 = erstelle_excel(a, tmp_path, ZEIT)
    assert p1 != p2 and p1.exists() and p2.exists()
    assert p2.name.endswith("_2.xlsx")


# ------------------------------------------------------------- Blatt HFS --

def test_hfs_staffeln(datei):
    hfs = load_workbook(datei)["HFS"]
    assert hfs["A2"].value == "10.01.2026 – 31.01.2026"
    assert (hfs["B2"].value, hfs["C2"].value) == (22, 1)
    assert (hfs["B3"].value, hfs["C3"].value) == (38, 0.5)
    assert hfs["C2"].number_format == "0%"
    assert hfs["B4"].value is None and hfs["B5"].value is None


def test_hfs_stundensatz_und_stunden_pro_tag_bleiben_leer(datei):
    hfs = load_workbook(datei)["HFS"]
    for r in range(2, 6):
        assert hfs.cell(row=r, column=4).value is None  # D Stundensatz
        assert hfs.cell(row=r, column=5).value is None  # E Stunden/Tag


def test_hfs_wochenstunden(datei):
    hfs = load_workbook(datei)["HFS"]
    assert hfs["B10"].value == 1.5  # Staubsaugen
    assert hfs["B20"].value == 7  # Kochen
    assert hfs["B21"].value == 2  # Wäsche waschen und aufhängen
    assert hfs["B22"].value is None  # Wäsche aufhängen (Excel) bleibt leer
    assert hfs["B28"].value == 3  # Gartenpflege
    assert hfs["B33"].value is None  # Reparaturarbeiten bleibt leer


def test_zuordnung_passt_zu_excel_beschriftung():
    hfs = load_workbook(TEMPLATE)["HFS"]
    abweichend = {"bad_feucht": "Sanitär feucht reinigen", "waesche_waschen": "Wäsche waschen",
                  "korrespondenz": "Korrespondenz", "sonstiges": "Sonstiges"}
    for t in TAETIGKEITEN:
        erwartet = abweichend.get(t["key"], t["label"])
        assert hfs.cell(row=t["hfs_row"], column=1).value.strip() == erwartet.strip(), t["key"]


def test_vorlage_sonst_unveraendert(datei):
    """Alle Zellen der Vorlage bleiben gleich – außer den befüllten HFS-Zellen."""
    vorlage = load_workbook(TEMPLATE)
    neu = load_workbook(datei)
    assert neu.sheetnames == ["Fragebogen", *vorlage.sheetnames]
    befuellt = {"A2", "B2", "C2", "A3", "B3", "C3", "B10", "B20", "B21", "B28"}
    for ws in vorlage.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if ws.title == "HFS" and c.coordinate in befuellt:
                    continue
                assert neu[ws.title][c.coordinate].value == c.value, f"{ws.title}!{c.coordinate}"
    assert neu["P-Sch"]["B4"].value == "=HFS!F6"
    assert neu["HFS"]["F2"].value == "=B2*C2*D2*E2"
    assert neu.calculation.fullCalcOnLoad is True


# ------------------------------------------------------ Blatt Fragebogen --

def test_fragebogen_ist_erstes_und_aktives_blatt(datei):
    wb = load_workbook(datei)
    assert wb.sheetnames[0] == "Fragebogen"
    assert wb.active.title == "Fragebogen"


def test_fragebogen_antworten(datei):
    t = texte(load_workbook(datei)["Fragebogen"])
    assert "Herr Jörg Müller-Lüdenscheidt" in t
    assert "03.11.2026, 14:05 Uhr" in t
    assert "Armbruch rechts" in t
    assert "10.01.2026 – 31.01.2026" in t
    assert "Ja – konkret: Rasen mähen" in t
    assert "15.02.2026" in t
    assert "200 qm" in t
    assert 13.5 in t  # Summe Wochenstunden


def test_fragebogen_enthaelt_alle_fragen_auch_unbeantwortet(tmp_path):
    minimal = Antwort(nachname="Muster", vorname="Max", einwilligung=True, installations_id="minimal-01")
    ws = load_workbook(erstelle_excel(minimal, tmp_path, ZEIT))["Fragebogen"]
    spalte_a = [c.value for c in ws["A"] if c.value]
    for frage in [
        "Wie viele Personen leben in Ihrem Haushalt (Sie eingeschlossen)?",
        "Haben Sie einen Garten?",
        "Haben Sie generell eine Haushaltshilfe?",
        "Welche Haushaltsgeräte besitzen Sie?",
    ]:
        assert frage in spalte_a
    for t in TAETIGKEITEN:
        assert spalte_a.count(t["label"]) == 2  # vor und nach dem Unfall
    for g in GERAETE:
        assert f"    {g['label']}" in spalte_a
    assert not any(str(v).startswith("Korrektur") for v in spalte_a)


def test_korrektur_wird_gekennzeichnet(tmp_path):
    k = Korrektur(datum=date(2026, 11, 2), datei="HFS_Muster_Max_2026-11-02_100000.xlsx")
    ws = load_workbook(erstelle_excel(Antwort(**beispiel()), tmp_path, ZEIT, k))["Fragebogen"]
    t = texte(ws)
    assert "Korrektur der Abgabe vom 02.11.2026" in t
    assert "vorherige Datei: HFS_Muster_Max_2026-11-02_100000.xlsx" in t


# ------------------------------------------------------------ Validierung --

@pytest.mark.parametrize("aenderung", [
    {"einwilligung": False},
    {"nachname": "  "},
    {"geraete": ["atomreaktor"]},
    {"taetigkeiten_vor": {"fliegen": {"aktiv": True}}},
    {"installations_id": "../../x"},
    {"staffeln": [{"von": "2026-02-01", "bis": "2026-01-01", "prozent": 50}]},
    {"staffeln": [{"von": "2026-01-01", "bis": "2026-01-02", "prozent": 150}]},
    {"staffeln": [{"von": "2026-01-01", "bis": "2026-01-02", "prozent": 10}] * 5},
    {"gehindert_von": "2026-03-01", "gehindert_bis": "2026-02-01"},
])
def test_ungueltige_angaben_werden_abgelehnt(aenderung):
    with pytest.raises(ValidationError):
        Antwort(**beispiel(**aenderung))
