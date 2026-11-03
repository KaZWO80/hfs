"""Web-App „Fragebogen Haushaltsführungsschaden“ (siehe plan/PLAN.md).

Start (Entwicklung, im Ordner server/):  uvicorn app:app --reload --port 8080

Umgebungsvariablen:
  HFS_DATEN_ORDNER      interne Daten (gespeicherte Antworten), Standard: ./daten
  HFS_ERGEBNIS_ORDNER   Excel-Dateien für die Kanzlei, Standard: <Daten>/ergebnisse

Abgabe-Regeln (Plan, Abschnitt 6), je Browser-Kennung:
  Fall A  noch nie abgegeben oder alle Excel-Dateien gelöscht -> leerer Fragebogen
  Fall B  heute bereits abgegeben -> Antworten nur lesen, keine Abgabe
  Fall C  an früherem Tag abgegeben -> vorausgefüllt, Abgabe = Korrektur (neue Datei)
"""

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import excel_export
from excel_export import Korrektur, erstelle_excel
from models import Antwort
from questionnaire import definition

BASIS = Path(__file__).parent
_lock = threading.Lock()
_ID_MUSTER = re.compile(r"^[A-Za-z0-9-]{8,64}$")

app = FastAPI(title="Fragebogen Haushaltsführungsschaden", docs_url=None, redoc_url=None, openapi_url=None)


# ---------------------------------------------------------------- Ablage ----

def daten_ordner() -> Path:
    return Path(os.environ.get("HFS_DATEN_ORDNER", BASIS / "daten"))


def ergebnis_ordner() -> Path:
    return Path(os.environ.get("HFS_ERGEBNIS_ORDNER", daten_ordner() / "ergebnisse"))


def _antwort_pfad(installations_id: str) -> Path:
    if not _ID_MUSTER.match(installations_id):
        raise HTTPException(400, "Ungültige Kennung")
    return daten_ordner() / "antworten" / f"{installations_id}.json"


def _lade_abgaben(installations_id: str) -> list[dict]:
    """Abgaben dieser Kennung, deren Excel-Datei noch existiert (älteste zuerst).

    Hat die Kanzlei alle Dateien gelöscht, werden auch die gespeicherten
    Antworten verworfen (-> Fall A, leerer Fragebogen).
    """
    p = _antwort_pfad(installations_id)
    if not p.exists():
        return []
    abgaben = [a for a in json.loads(p.read_text("utf-8")) if (ergebnis_ordner() / a["datei"]).exists()]
    if not abgaben:
        p.unlink()
    return abgaben


def _speichere_abgaben(installations_id: str, abgaben: list[dict]) -> None:
    p = _antwort_pfad(installations_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(abgaben, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(p)


def _status(abgaben: list[dict], heute) -> dict:
    if not abgaben:
        return {"fall": "A"}
    letzte = abgaben[-1]
    zeit = datetime.fromisoformat(letzte["zeit"])
    return {
        "fall": "B" if zeit.date() == heute else "C",
        "abgegeben_am": zeit.strftime("%d.%m.%Y"),
        "abgegeben_um": zeit.strftime("%H:%M"),
        "antwort": letzte["antwort"],
    }


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


@app.get("/api/status/{installations_id}")
def status(installations_id: str):
    with _lock:
        return _status(_lade_abgaben(installations_id), excel_export.jetzt().date())


@app.post("/api/antwort", status_code=201)
def antwort_speichern(antwort: Antwort):
    with _lock:
        zeit = excel_export.jetzt()
        abgaben = _lade_abgaben(antwort.installations_id)
        st = _status(abgaben, zeit.date())
        if st["fall"] == "B":
            raise HTTPException(409, "Sie haben den Fragebogen heute bereits abgegeben. Änderungen sind ab morgen möglich.")
        korrektur = None
        if st["fall"] == "C":
            vorher = abgaben[-1]
            korrektur = Korrektur(datetime.fromisoformat(vorher["zeit"]).date(), vorher["datei"])
        pfad = erstelle_excel(antwort, ergebnis_ordner(), zeit, korrektur)
        abgaben.append({
            "zeit": zeit.isoformat(timespec="seconds"),
            "datei": pfad.name,
            "antwort": antwort.model_dump(mode="json", exclude={"installations_id"}),
        })
        _speichere_abgaben(antwort.installations_id, abgaben)
    return {"ok": True, "korrektur": korrektur is not None}


@app.exception_handler(HTTPException)
async def http_fehler(request: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


app.mount("/", StaticFiles(directory=BASIS / "static", html=True), name="static")
