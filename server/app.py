"""Web-App „Fragebogen Haushaltsführungsschaden“ (siehe plan/PLAN.md).

Start (Entwicklung, im Ordner server/):  uvicorn app:app --reload --port 8080

Umgebungsvariable:
  HFS_ERGEBNIS_ORDNER   Excel-Dateien für die Kanzlei, Standard: ./daten/ergebnisse

Aktenzeichen-Verfahren (Plan, Abschnitt 12.2):
  * Anmeldung mit Aktenzeichen + Nachname.
  * Vorhandene Datei zum Aktenzeichen -> Vorschlagswerte aus der neuesten Datei,
    aber nur, wenn der Nachname passt.
  * Jede Abgabe mit Änderungen erzeugt eine neue Datei; unveränderte Abgaben
    werden abgelehnt. Die Excel-Dateien sind die einzige Datenquelle.
"""

import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import excel_export
from excel_export import Korrektur, abgaben, erstelle_excel, lade_antwort
from models import AKTENZEICHEN_MUSTER, Antwort, name_vergleich
from questionnaire import definition

BASIS = Path(__file__).parent
_lock = threading.Lock()

# Schutz gegen Durchprobieren: max. 10 Fehlversuche in 15 Minuten,
# gezählt je Aktenzeichen und je Absender-Adresse.
MAX_FEHLVERSUCHE = 10
SPERRZEIT = 15 * 60
_fehlversuche: dict[str, deque] = defaultdict(deque)

FALSCHER_NAME = ("Aktenzeichen und Nachname passen nicht zusammen. Bitte prüfen Sie Ihre Eingabe "
                 "oder wenden Sie sich an die Kanzlei.")
GESPERRT = "Zu viele Fehlversuche. Bitte versuchen Sie es in 15 Minuten erneut."

app = FastAPI(title="Fragebogen Haushaltsführungsschaden", docs_url=None, redoc_url=None, openapi_url=None)


def ergebnis_ordner() -> Path:
    return Path(os.environ.get("HFS_ERGEBNIS_ORDNER", BASIS / "daten" / "ergebnisse"))


# ------------------------------------------------------- Fehlversuche ------

def _schluessel(request: Request, aktenzeichen: str) -> list[str]:
    absender = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "?")
    return [f"ip:{absender}", f"az:{excel_export.dateiname_teil(aktenzeichen).lower()}"]


def _gesperrt(schluessel: list[str]) -> bool:
    grenze = time.monotonic() - SPERRZEIT
    for k in schluessel:
        q = _fehlversuche[k]
        while q and q[0] < grenze:
            q.popleft()
        if len(q) >= MAX_FEHLVERSUCHE:
            return True
    return False


def _fehlversuch(schluessel: list[str]) -> None:
    for k in schluessel:
        _fehlversuche[k].append(time.monotonic())


# ------------------------------------------------------- Datei-Zugriff -----

def _neueste(aktenzeichen: str):
    """Neueste lesbare Abgabe (Abgabe, Antwort-dict) oder (None, None)."""
    for abgabe in reversed(abgaben(ergebnis_ordner(), aktenzeichen)):
        daten = lade_antwort(abgabe.pfad)
        if daten is not None:
            return abgabe, daten
    return None, None


def _pruefe_zugang(request: Request, aktenzeichen: str, nachname: str):
    """Liefert (Abgabe, Antwort) der neuesten Datei oder (None, None) bei neuem
    Aktenzeichen. Wirft 403 bei falschem Nachnamen, 429 bei Sperre."""
    schluessel = _schluessel(request, aktenzeichen)
    if _gesperrt(schluessel):
        raise HTTPException(429, GESPERRT)
    abgabe, daten = _neueste(aktenzeichen)
    if abgabe and name_vergleich(daten.get("nachname", "")) != name_vergleich(nachname):
        _fehlversuch(schluessel)
        raise HTTPException(403, FALSCHER_NAME)
    return abgabe, daten


# ------------------------------------------------------------------- API ----

@app.middleware("http")
async def sicherheits_header(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/fragebogen")
def fragebogen():
    return definition()


class Anmeldung(BaseModel):
    aktenzeichen: str = Field(min_length=1, max_length=30, pattern=AKTENZEICHEN_MUSTER)
    nachname: str = Field(min_length=1, max_length=80)


@app.post("/api/anmelden")
def anmelden(daten: Anmeldung, request: Request):
    az = daten.aktenzeichen.strip()
    with _lock:
        abgabe, antwort = _pruefe_zugang(request, az, daten.nachname)
    if not abgabe:
        return {"vorhanden": False}
    antwort.pop("einwilligung", None)
    return {
        "vorhanden": True,
        "stand": abgabe.stand,
        "abgegeben_am": abgabe.zeit.strftime("%d.%m.%Y"),
        "abgegeben_um": abgabe.zeit.strftime("%H:%M"),
        "antwort": antwort,
    }


@app.post("/api/antwort", status_code=201)
def antwort_speichern(antwort: Antwort, request: Request):
    with _lock:
        abgabe, vorher = _pruefe_zugang(request, antwort.aktenzeichen, antwort.nachname)
        korrektur = None
        if abgabe:
            try:
                vorher_vergleich = Antwort.model_validate({**vorher, "einwilligung": True}).vergleichsdaten()
            except ValueError:  # ältere Abgabe erfüllt neuere Prüfregeln nicht -> gilt als geändert
                vorher_vergleich = None
            if vorher_vergleich == antwort.vergleichsdaten():
                raise HTTPException(409, "Sie haben nichts geändert. Ihre Angaben vom "
                                         f"{abgabe.zeit:%d.%m.%Y} liegen der Kanzlei bereits vor.")
            korrektur = Korrektur(abgabe.zeit.date(), abgabe.pfad.name)
        pfad = erstelle_excel(antwort, ergebnis_ordner(), excel_export.jetzt(), korrektur)
        neu = next(x for x in abgaben(ergebnis_ordner(), antwort.aktenzeichen) if x.pfad == pfad)
    return {"ok": True, "korrektur": korrektur is not None, "stand": neu.stand,
            "abgegeben_am": neu.zeit.strftime("%d.%m.%Y"), "abgegeben_um": neu.zeit.strftime("%H:%M")}


@app.exception_handler(HTTPException)
async def http_fehler(request: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


app.mount("/", StaticFiles(directory=BASIS / "static", html=True), name="static")
