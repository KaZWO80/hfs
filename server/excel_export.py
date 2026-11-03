"""Erzeugt pro Fragebogen eine Excel-Datei auf Basis der Vorlage
``templates/Anspruchsberechnungen.xlsx`` (siehe plan/PLAN.md, Abschnitt 5).

* Neues erstes Blatt "Fragebogen": alle Fragen samt Antworten,
  auch unbeantwortete Fragen werden aufgeführt.
* Blatt "HFS" wird vorbefüllt:
  - Zeilen 2-5: Zeitraum (A), Tage (B), Anteil der Beeinträchtigung (C).
    Stundensatz (D) und Stunden/Tag (E) bleiben leer (Kanzlei).
  - Zeilen 10-34, Spalte B: wöchentlicher Zeitaufwand je Tätigkeit.
* Alle übrigen Blätter und Formeln der Vorlage bleiben unverändert.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from models import Antwort
from questionnaire import GERAETE, TAETIGKEITEN

TEMPLATE = Path(__file__).parent / "templates" / "Anspruchsberechnungen.xlsx"
ZEITZONE = ZoneInfo("Europe/Berlin")

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


@dataclass
class Korrektur:
    """Hinweis auf die vorherige Abgabe, wenn es sich um eine Korrektur handelt."""

    datum: date
    datei: str


def jetzt() -> datetime:
    return datetime.now(ZEITZONE)


def dateiname_teil(text: str) -> str:
    """Macht aus einem Namen einen sicheren Dateinamen-Bestandteil."""
    text = text.strip().translate(_UMLAUTE)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9-]+", "-", text).strip("-")
    return text[:40] or "unbekannt"


def dateiname(antwort: Antwort, zeitpunkt: datetime, zusatz: str = "") -> str:
    return (
        f"HFS_{dateiname_teil(antwort.nachname)}_{dateiname_teil(antwort.vorname)}_"
        f"{zeitpunkt:%Y-%m-%d_%H%M%S}{zusatz}.xlsx"
    )


# ------------------------------------------------------------ Formatierung --

def _d(v: date | None) -> str:
    return v.strftime("%d.%m.%Y") if v else ""


def _janein(v: bool | None) -> str:
    return {True: "Ja", False: "Nein", None: ""}[v]


def _zahl(v):
    """Zahlen als echte Zahl in die Zelle (Excel kann damit rechnen)."""
    return v if v is not None else None


def _zeitraum(von: date | None, bis: date | None) -> str:
    if not von and not bis:
        return ""
    return f"{_d(von) or '?'} – {_d(bis) or '?'}"


# ------------------------------------------------------- Blatt Fragebogen --

class _Schreiber:
    FETT = Font(bold=True)
    TITEL = Font(bold=True, size=14)
    HINWEIS = Font(italic=True, color="9C0006")
    KOPF = PatternFill("solid", fgColor="DDE7F0")
    TABKOPF = PatternFill("solid", fgColor="F2F2F2")
    UMBRUCH = Alignment(wrap_text=True, vertical="top")
    MITTE = Alignment(wrap_text=True, vertical="top", horizontal="center")
    LINIE = Border(bottom=Side(style="hair", color="BFBFBF"))

    def __init__(self, ws):
        self.ws = ws
        self.zeile = 1

    def add(self, *werte, font=None, fill=None, linie=True):
        for i, w in enumerate(werte, start=1):
            c = self.ws.cell(row=self.zeile, column=i, value=w if w != "" else None)
            c.alignment = self.MITTE if i == 2 else self.UMBRUCH
            if font:
                c.font = font
            if fill:
                c.fill = fill
            if linie:
                c.border = self.LINIE
        self.zeile += 1

    def abschnitt(self, text):
        self.zeile += 1
        self.add(text, None, None, font=self.FETT, fill=self.KOPF, linie=False)
        r = self.zeile - 1
        self.ws.cell(row=r, column=1).alignment = self.UMBRUCH
        self.ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)

    def tabkopf(self, *werte):
        self.add(*werte, font=self.FETT, fill=self.TABKOPF)


def _blatt_fragebogen(wb, a: Antwort, zeitpunkt: datetime, korrektur: Korrektur | None):
    ws = wb.create_sheet("Fragebogen", 0)
    ws.column_dimensions["A"].width = 58
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 60
    ws.sheet_view.zoomScale = 100
    s = _Schreiber(ws)

    s.add("Haushaltsführungsschaden – Fragebogen", font=s.TITEL, linie=False)
    s.add("Name", f"{a.anrede} {a.vorname} {a.nachname}".strip())
    s.add("Eingegangen am", zeitpunkt.strftime("%d.%m.%Y, %H:%M Uhr"))
    if korrektur:
        s.add(
            f"Korrektur der Abgabe vom {_d(korrektur.datum)}",
            None,
            f"vorherige Datei: {korrektur.datei}",
            font=s.HINWEIS,
        )

    # 1 -----------------------------------------------------------------
    s.abschnitt("1. Haushaltsführung und Beeinträchtigung")
    s.add("Wie war die Haushaltsführung vor dem Unfall aufgeteilt? – Ich (%)", _zahl(a.anteil_ich_prozent))
    s.add("Wie war die Haushaltsführung vor dem Unfall aufgeteilt? – Andere (%)", _zahl(a.anteil_andere_prozent))
    s.add(
        "Über welchen Zeitraum waren Sie unfallbedingt konkret daran gehindert, "
        "Ihre Haushaltsführung wie üblich durchzuführen?",
        _zeitraum(a.gehindert_von, a.gehindert_bis),
    )
    s.add(
        "Warum waren Sie konkret daran gehindert, Ihre Haushaltsführung wie üblich durchzuführen?",
        None,
        a.gehindert_grund,
    )
    s.add(
        "Bitte schätzen Sie Ihren Grad der jeweiligen unfallbedingten Beeinträchtigung "
        "in der Haushaltsführung in Prozent (ggf. gestaffelt):",
    )
    if a.staffeln:
        s.tabkopf("Zeitraum", "Beeinträchtigung", "Tage")
        for st in a.staffeln:
            s.add(_zeitraum(st.von, st.bis), st.prozent / 100, st.tage)
            ws.cell(row=s.zeile - 1, column=2).number_format = "0%"
    s.add(
        "Bei welchen alltäglichen Bewegungen, Tätigkeiten haben Sie unfallbedingt konkret "
        "welche Schmerzen gehabt (Arbeit, Sport, beim Schlafen, beim Sitzen etc.)?",
        None,
        a.schmerzen,
    )

    # 2 -----------------------------------------------------------------
    s.abschnitt("2. Haushalt und Wohnsituation")
    s.add("Wie viele Personen leben in Ihrem Haushalt (Sie eingeschlossen)?", _zahl(a.personen))
    s.add("Falls Sie Kinder haben, wie alt sind diese?", a.kinder_alter)
    s.add("Wie ist Ihre Wohnsituation? – Haus / Wohnung", a.wohnform)
    s.add("Wie ist Ihre Wohnsituation? – Eigentum / Miete", a.wohnverhaeltnis)
    s.add("Wie viele Quadratmeter bewohnen Sie?", _zahl(a.wohnflaeche_qm))
    s.add("Wie viele Räume bewohnen Sie?", _zahl(a.raeume))
    s.add("Auf wie vielen Etagen wohnen Sie?", _zahl(a.etagen))
    s.add(
        "Gibt es Besonderheiten (z. B. ungünstig, eng / günstig, großzügig geschnittene Räume)?",
        None,
        a.besonderheiten,
    )
    s.add("Haben Sie einen Garten?", _janein(a.garten), f"{a.garten_qm:g} qm" if a.garten and a.garten_qm else None)
    s.add("Welche Haushaltsgeräte besitzen Sie?", None, None)
    for g in GERAETE:
        s.add(f"    {g['label']}", "Ja" if g["key"] in a.geraete else "Nein")
    s.add("    Sonstiges", None, a.geraete_sonstiges)
    s.add("Haben Sie generell eine Haushaltshilfe?", _janein(a.haushaltshilfe_generell))
    s.add(
        "Hatten Sie während der unfallbedingten Einschränkungen eine bezahlte Haushaltshilfe?",
        _janein(a.bezahlte_hilfe),
        _zeitraum(a.bezahlte_hilfe_von, a.bezahlte_hilfe_bis) if a.bezahlte_hilfe else None,
    )
    s.add("    für welche Tätigkeiten?", None, a.bezahlte_hilfe_taetigkeiten if a.bezahlte_hilfe else None)

    # 3 -----------------------------------------------------------------
    s.abschnitt("3. Welche Tätigkeiten gehörten vor dem Unfall zu Ihrem Aufgabenbereich?")
    s.tabkopf("Tätigkeit", "Wöchentlicher Zeitaufwand in Stunden (ca.)", "Angekreuzt / Angaben")
    summe = 0.0
    for t in TAETIGKEITEN:
        v = a.taetigkeiten_vor.get(t["key"])
        aktiv = bool(v and (v.aktiv or v.stunden_pro_woche))
        stunden = v.stunden_pro_woche if v else None
        summe += stunden or 0
        angaben = "Ja" if aktiv else "Nein"
        if v and v.detail:
            angaben += f" – {t.get('detail', '')} {v.detail}".replace("  ", " ")
        s.add(t["label"], stunden, angaben)
    s.add("Summe", summe, None, font=s.FETT)

    # 4 -----------------------------------------------------------------
    s.abschnitt(
        "4. Bei welchen Tätigkeiten waren Sie nach dem Unfall konkret beeinträchtigt? "
        "Ab wann war die Tätigkeit wieder möglich?"
    )
    s.tabkopf("Tätigkeit", "Beeinträchtigt", "Ab wann war die Tätigkeit wieder möglich?")
    for t in TAETIGKEITEN:
        v = a.taetigkeiten_nach.get(t["key"])
        if v and v.beeintraechtigt:
            s.add(t["label"], "Ja", _d(v.wieder_moeglich_ab) or "noch nicht wieder möglich")
        else:
            s.add(t["label"], "Nein", None)

    # 5 -----------------------------------------------------------------
    s.abschnitt("5. Einwilligung")
    s.add("Einwilligung zur Verarbeitung der Angaben (inkl. Gesundheitsdaten) erteilt", _janein(a.einwilligung))

    ws.print_title_rows = "1:1"
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return ws


# -------------------------------------------------------------- Blatt HFS --

def _blatt_hfs(wb, a: Antwort):
    ws = wb["HFS"]
    for i, st in enumerate(a.staffeln):
        r = 2 + i
        ws.cell(row=r, column=1, value=_zeitraum(st.von, st.bis))
        ws.cell(row=r, column=2, value=st.tage)
        ws.cell(row=r, column=3, value=st.prozent / 100).number_format = "0%"
        # D (Stundensatz) und E (Stunden/Tag) bleiben leer – Entscheidung 1 und 2.
    for t in TAETIGKEITEN:
        v = a.taetigkeiten_vor.get(t["key"])
        if v and v.stunden_pro_woche:
            ws.cell(row=t["hfs_row"], column=2, value=v.stunden_pro_woche)
    if a.staffeln and (ws.column_dimensions["A"].width or 0) < 24:
        ws.column_dimensions["A"].width = 24  # Platz für "TT.MM.JJJJ – TT.MM.JJJJ"


# ------------------------------------------------------------------ Export --

def erstelle_excel(
    antwort: Antwort,
    ziel_ordner: Path,
    zeitpunkt: datetime | None = None,
    korrektur: Korrektur | None = None,
) -> Path:
    zeitpunkt = zeitpunkt or jetzt()
    wb = load_workbook(TEMPLATE)
    _blatt_hfs(wb, antwort)
    ws = _blatt_fragebogen(wb, antwort, zeitpunkt, korrektur)
    wb.active = wb.index(ws)
    for blatt in wb.worksheets:
        blatt.sheet_view.tabSelected = blatt is ws
    # Excel soll beim Öffnen alle Formeln neu berechnen (HFS -> P-Sch -> S-Sch).
    wb.calculation.fullCalcOnLoad = True

    ziel_ordner.mkdir(parents=True, exist_ok=True)
    pfad = ziel_ordner / dateiname(antwort, zeitpunkt)
    n = 2
    while pfad.exists():
        pfad = ziel_ordner / dateiname(antwort, zeitpunkt, f"_{n}")
        n += 1
    wb.save(pfad)
    return pfad
