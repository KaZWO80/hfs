"""Datenmodell einer Fragebogen-Antwort (Validierung auf dem Server)."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from questionnaire import GERAET_KEYS, MAX_STAFFELN, TAETIGKEIT_KEYS

Kurztext = Field(default="", max_length=200)
Langtext = Field(default="", max_length=5000)


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

    # Technik / Recht
    einwilligung: bool
    installations_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")

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
        return self
