"""Datenmodell einer Fragebogen-Antwort (Validierung auf dem Server)."""

import re
import unicodedata
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from questionnaire import GERAET_KEYS, MAX_STAFFELN, TAETIGKEIT_KEYS

Kurztext = Field(default="", max_length=200)
Langtext = Field(default="", max_length=5000)

# Aktenzeichen, wie die Kanzlei es vergibt, z. B. "123/26" oder "HFS-2026-0042".
AKTENZEICHEN_MUSTER = r"^[A-Za-z0-9ÄÖÜäöüß][A-Za-z0-9ÄÖÜäöüß /.\-_]{0,29}$"

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def ascii_text(text: str) -> str:
    """Umlaute umschreiben (ä -> ae) und übrige Akzente entfernen."""
    text = text.strip().translate(_UMLAUTE)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def name_vergleich(name: str) -> str:
    """Vergleichsform eines Nachnamens: ohne Groß-/Kleinschreibung, Leer- und
    Sonderzeichen; "Müller-Lüdenscheidt" == "mueller luedenscheidt"."""
    return re.sub(r"[^a-z0-9]", "", ascii_text(name).lower())


class Staffel(BaseModel):
    """Ein Zeitraum mit gleichem Grad der Beeinträchtigung."""

    von: date
    bis: date
    prozent: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _reihenfolge(self):
        if self.bis < self.von:
            raise ValueError("'bis' liegt vor 'von'")
        return self

    @property
    def tage(self) -> int:
        return (self.bis - self.von).days + 1


class TaetigkeitVor(BaseModel):
    aktiv: bool = False
    stunden_pro_woche: Optional[float] = Field(default=None, ge=0, le=168)
    detail: str = Kurztext

    @model_validator(mode="after")
    def _stunden_pflicht(self):
        if self.aktiv and not (self.stunden_pro_woche and self.stunden_pro_woche > 0):
            raise ValueError("Bei angehakter Tätigkeit sind die Stunden pro Woche (mehr als 0) Pflicht.")
        return self


class TaetigkeitNach(BaseModel):
    beeintraechtigt: bool = False
    wieder_moeglich_ab: Optional[date] = None
    hinweis: str = Kurztext


class Antwort(BaseModel):
    # Person
    nachname: str = Field(min_length=1, max_length=80)
    vorname: str = Field(min_length=1, max_length=80)
    anrede: Literal["", "Frau", "Herr", "Divers"] = ""

    # Aufteilung und Zeitraum
    anteil_ich_prozent: Optional[float] = Field(default=None, ge=0, le=100)
    anteil_andere_prozent: Optional[float] = Field(default=None, ge=0, le=100)
    gehindert_von: Optional[date] = None
    gehindert_bis: Optional[date] = None
    gehindert_grund: str = Langtext
    staffeln: list[Staffel] = Field(default_factory=list, max_length=MAX_STAFFELN)
    schmerzen: str = Langtext

    # Haushalt und Wohnung
    personen: Optional[int] = Field(default=None, ge=1, le=30)
    kinder_alter: str = Kurztext
    wohnform: Literal["", "Haus", "Wohnung"] = ""
    wohnverhaeltnis: Literal["", "Eigentum", "Miete"] = ""
    wohnflaeche_qm: Optional[float] = Field(default=None, ge=0, le=10000)
    raeume: Optional[int] = Field(default=None, ge=0, le=100)
    etagen: Optional[int] = Field(default=None, ge=0, le=20)
    besonderheiten: str = Langtext
    garten: Optional[bool] = None
    garten_qm: Optional[float] = Field(default=None, ge=0, le=1000000)

    geraete: list[str] = Field(default_factory=list)
    geraete_sonstiges: str = Kurztext

    haushaltshilfe_generell: Optional[bool] = None
    bezahlte_hilfe: Optional[bool] = None
    bezahlte_hilfe_von: Optional[date] = None
    bezahlte_hilfe_bis: Optional[date] = None
    bezahlte_hilfe_taetigkeiten: str = Langtext

    taetigkeiten_vor: dict[str, TaetigkeitVor] = Field(default_factory=dict)
    taetigkeiten_nach: dict[str, TaetigkeitNach] = Field(default_factory=dict)

    # Zuordnung / Recht
    aktenzeichen: str = Field(min_length=1, max_length=30, pattern=AKTENZEICHEN_MUSTER)
    einwilligung: bool

    @field_validator("aktenzeichen", mode="before")
    @classmethod
    def _az_strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("nachname", "vorname")
    @classmethod
    def _name_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("darf nicht leer sein")
        return v

    @field_validator("geraete")
    @classmethod
    def _geraete(cls, v: list[str]) -> list[str]:
        unbekannt = set(v) - GERAET_KEYS
        if unbekannt:
            raise ValueError(f"unbekannte Geräte: {sorted(unbekannt)}")
        return v

    @field_validator("taetigkeiten_vor", "taetigkeiten_nach")
    @classmethod
    def _taetigkeiten(cls, v: dict) -> dict:
        unbekannt = set(v) - TAETIGKEIT_KEYS
        if unbekannt:
            raise ValueError(f"unbekannte Tätigkeiten: {sorted(unbekannt)}")
        return v

    @model_validator(mode="after")
    def _pruefungen(self):
        if not self.einwilligung:
            raise ValueError("Die Einwilligung zur Datenverarbeitung ist erforderlich.")
        if self.gehindert_von and self.gehindert_bis and self.gehindert_bis < self.gehindert_von:
            raise ValueError("Zeitraum der Verhinderung: 'bis' liegt vor 'von'")
        ich, andere = self.anteil_ich_prozent, self.anteil_andere_prozent
        if (ich is None) != (andere is None) or (ich is not None and abs(ich + andere - 100) > 0.001):
            raise ValueError("Aufteilung der Haushaltsführung: 'Ich' und 'Andere' müssen zusammen 100 % ergeben.")
        return self

    def vergleichsdaten(self) -> dict:
        """Inhalt ohne Einwilligung/Aktenzeichen – zum Erkennen unveränderter Abgaben."""
        return self.model_dump(mode="json", exclude={"einwilligung", "aktenzeichen"})
