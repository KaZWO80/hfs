import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_modul  # noqa: E402
import excel_export  # noqa: E402
from excel_export import ZEITZONE  # noqa: E402
from test_excel import beispiel  # noqa: E402

AZ = "123/26"
NAME = "Müller-Lüdenscheidt"


class Uhr:
    def __init__(self):
        self.zeit = datetime(2026, 11, 4, 10, 0, 0, tzinfo=ZEITZONE)

    def __call__(self):
        return self.zeit

    def stelle(self, *args):
        self.zeit = datetime(*args, tzinfo=ZEITZONE)


@pytest.fixture
def uhr(monkeypatch):
    u = Uhr()
    monkeypatch.setattr(excel_export, "jetzt", u)
    return u


@pytest.fixture
def ordner(tmp_path, monkeypatch):
    monkeypatch.setenv("HFS_ERGEBNIS_ORDNER", str(tmp_path / "ergebnisse"))
    app_modul._fehlversuche.clear()
    return tmp_path / "ergebnisse"


@pytest.fixture
def client(ordner, uhr):
    return TestClient(app_modul.app)


def dateien(ordner):
    return sorted(p.name for p in ordner.glob("*.xlsx"))


def anmelden(client, az=AZ, name=NAME, **kw):
    return client.post("/api/anmelden", json={"aktenzeichen": az, "nachname": name}, **kw)


def test_ablauf_neu_vorhanden_korrektur(client, uhr, ordner):
    # neues Aktenzeichen -> leerer Fragebogen
    assert anmelden(client).json() == {"vorhanden": False}
    r = client.post("/api/antwort", json=beispiel())
    assert r.status_code == 201 and r.json()["korrektur"] is False
    assert dateien(ordner) == ["HFS_123-26_2026-11-04_100000.xlsx"]

    # erneute Anmeldung -> Vorschlagswerte aus der Datei
    st = anmelden(client).json()
    assert st["vorhanden"] is True
    assert (st["abgegeben_am"], st["abgegeben_um"], st["stand"]) == ("04.11.2026", "10:00", "2026-11-04_100000")
    assert st["antwort"]["taetigkeiten_vor"]["kochen"]["stunden_pro_woche"] == 7
    assert "einwilligung" not in st["antwort"]

    # unverändert erneut senden -> abgelehnt, keine neue Datei
    uhr.stelle(2026, 11, 4, 10, 5, 0)
    r = client.post("/api/antwort", json=beispiel())
    assert r.status_code == 409 and "nichts geändert" in r.json()["detail"]
    assert len(dateien(ordner)) == 1

    # geändert -> neue Datei mit Korrekturvermerk, alte bleibt (auch am selben Tag)
    r = client.post("/api/antwort", json=beispiel(gehindert_grund="Armbruch rechts und Prellung"))
    assert r.status_code == 201 and r.json()["korrektur"] is True
    assert dateien(ordner) == ["HFS_123-26_2026-11-04_100000.xlsx", "HFS_123-26_2026-11-04_100500.xlsx"]
    werte = [c.value for row in load_workbook(ordner / dateien(ordner)[1])["Fragebogen"].iter_rows()
             for c in row if c.value]
    assert "Korrektur der Abgabe vom 04.11.2026" in werte
    assert "vorherige Datei: HFS_123-26_2026-11-04_100000.xlsx" in werte

    # Vorschlagswerte kommen immer aus der neuesten Datei
    assert anmelden(client).json()["antwort"]["gehindert_grund"] == "Armbruch rechts und Prellung"


def test_nachname_wird_tolerant_verglichen(client, ordner):
    client.post("/api/antwort", json=beispiel())
    for name in ["müller-lüdenscheidt", "Mueller Luedenscheidt", "  MÜLLER-LÜDENSCHEIDT "]:
        assert anmelden(client, name=name).json()["vorhanden"] is True
    assert anmelden(client, az="123-26").json()["vorhanden"] is True  # gleiche Schreibweise im Dateinamen


def test_falscher_nachname_zeigt_keine_daten(client, ordner):
    client.post("/api/antwort", json=beispiel())
    r = anmelden(client, name="Meier")
    assert r.status_code == 403
    assert "passen nicht zusammen" in r.json()["detail"] and "antwort" not in r.json()
    # auch Absenden unter fremdem Namen wird abgelehnt
    assert client.post("/api/antwort", json=beispiel(nachname="Meier")).status_code == 403
    assert len(dateien(ordner)) == 1


def test_sperre_nach_zehn_fehlversuchen(client, ordner):
    client.post("/api/antwort", json=beispiel())
    for _ in range(10):
        assert anmelden(client, name="Falsch").status_code == 403
    # jetzt gesperrt – auch mit richtigem Namen
    r = anmelden(client)
    assert r.status_code == 429 and "15 Minuten" in r.json()["detail"]
    # anderes Aktenzeichen von anderer Adresse bleibt nutzbar
    andere = anmelden(client, az="999/26", name="Neu", headers={"X-Forwarded-For": "10.0.0.9"})
    assert andere.status_code == 200


def test_sperre_endet_nach_15_minuten(client, ordner, monkeypatch):
    client.post("/api/antwort", json=beispiel())
    t = [1000.0]
    monkeypatch.setattr(app_modul.time, "monotonic", lambda: t[0])
    for _ in range(10):
        anmelden(client, name="Falsch")
    assert anmelden(client).status_code == 429
    t[0] += 15 * 60 + 1
    assert anmelden(client).status_code == 200


def test_kanzlei_loescht_dateien(client, uhr, ordner):
    client.post("/api/antwort", json=beispiel(gehindert_grund="erste"))
    uhr.stelle(2026, 11, 5, 9, 0, 0)
    client.post("/api/antwort", json=beispiel(gehindert_grund="zweite"))
    # nur neueste gelöscht -> vorherige Abgabe ist wieder Vorschlag
    (ordner / "HFS_123-26_2026-11-05_090000.xlsx").unlink()
    assert anmelden(client).json()["antwort"]["gehindert_grund"] == "erste"
    # alle gelöscht -> neu beantworten, auch mit anderem Namen
    for p in ordner.glob("*.xlsx"):
        p.unlink()
    assert anmelden(client, name="Neuer Name").json() == {"vorhanden": False}


def test_aktenzeichen_sind_unabhaengig(client, ordner):
    client.post("/api/antwort", json=beispiel())
    client.post("/api/antwort", json=beispiel(aktenzeichen="124/26", nachname="Schmidt"))
    assert anmelden(client, az="124/26", name="Schmidt").json()["antwort"]["nachname"] == "Schmidt"
    assert anmelden(client, az="125/26", name="Egal").json() == {"vorhanden": False}


def test_validierung(client, ordner):
    assert client.post("/api/antwort", json=beispiel(einwilligung=False)).status_code == 422
    assert client.post("/api/antwort", json=beispiel(anteil_ich_prozent=70, anteil_andere_prozent=20)).status_code == 422
    assert anmelden(client, az="../../etc").status_code == 422
    assert anmelden(client, az="").status_code == 422
    assert dateien(ordner) == []


def test_seiten_und_sicherheitsheader(client):
    r = client.get("/")
    assert r.status_code == 200 and "Aktenzeichen" in r.text
    assert r.headers["content-security-policy"].startswith("default-src 'self'")
    assert client.get("/datenschutz.html").status_code == 200
    assert client.get("/api/fragebogen").json()["max_staffeln"] == 4
    assert client.get("/docs").status_code == 404


def test_aeltere_abgabe_ohne_stunden_kann_korrigiert_werden(client, uhr, ordner):
    """Abgaben aus der Zeit vor der Stunden-Pflicht dienen weiter als Vorschlag
    und lassen sich korrigieren."""
    import json
    client.post("/api/antwort", json=beispiel())
    pfad = next(ordner.glob("*.xlsx"))
    wb = load_workbook(pfad)
    daten = json.loads(wb["_Daten"]["A2"].value)
    daten["taetigkeiten_vor"]["kochen"]["stunden_pro_woche"] = None  # wie eine alte Abgabe
    wb["_Daten"]["A2"] = json.dumps(daten, ensure_ascii=False)
    wb.save(pfad)

    st = anmelden(client).json()
    assert st["vorhanden"] and st["antwort"]["taetigkeiten_vor"]["kochen"]["stunden_pro_woche"] is None
    uhr.stelle(2026, 11, 4, 11, 0, 0)
    r = client.post("/api/antwort", json=beispiel())
    assert r.status_code == 201 and r.json()["korrektur"] is True
