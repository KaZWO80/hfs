import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import excel_export  # noqa: E402
from excel_export import ZEITZONE  # noqa: E402
from test_excel import beispiel  # noqa: E402

ID = "test-1234-abcd"


class Uhr:
    def __init__(self):
        self.zeit = datetime(2026, 11, 3, 10, 0, 0, tzinfo=ZEITZONE)

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
    monkeypatch.setenv("HFS_DATEN_ORDNER", str(tmp_path / "daten"))
    monkeypatch.setenv("HFS_ERGEBNIS_ORDNER", str(tmp_path / "ergebnisse"))
    return tmp_path / "ergebnisse"


@pytest.fixture
def client(ordner, uhr):
    from app import app

    return TestClient(app)


def dateien(ordner):
    return sorted(p.name for p in ordner.glob("*.xlsx"))


def test_fall_a_b_c_ablauf(client, uhr, ordner):
    # Fall A: noch nichts abgegeben
    assert client.get(f"/api/status/{ID}").json() == {"fall": "A"}
    r = client.post("/api/antwort", json=beispiel())
    assert r.status_code == 201 and r.json() == {"ok": True, "korrektur": False}
    assert dateien(ordner) == ["HFS_Mueller-Luedenscheidt_Joerg_2026-11-03_100000.xlsx"]

    # Fall B: gleicher Tag -> nur lesen, Abgabe gesperrt
    uhr.stelle(2026, 11, 3, 23, 59, 0)
    st = client.get(f"/api/status/{ID}").json()
    assert st["fall"] == "B"
    assert st["abgegeben_am"] == "03.11.2026" and st["abgegeben_um"] == "10:00"
    assert st["antwort"]["nachname"] == "Müller-Lüdenscheidt"
    assert st["antwort"]["taetigkeiten_vor"]["kochen"]["stunden_pro_woche"] == 7
    assert "installations_id" not in st["antwort"]
    assert client.post("/api/antwort", json=beispiel(gehindert_grund="geändert")).status_code == 409
    assert len(dateien(ordner)) == 1

    # Fall C: nächster Tag (ab 0:00 Uhr) -> Korrektur in neue Datei, alte bleibt
    uhr.stelle(2026, 11, 4, 0, 0, 1)
    st = client.get(f"/api/status/{ID}").json()
    assert st["fall"] == "C" and st["abgegeben_am"] == "03.11.2026"
    r = client.post("/api/antwort", json=beispiel(gehindert_grund="Armbruch rechts und Prellung"))
    assert r.status_code == 201 and r.json()["korrektur"] is True
    assert dateien(ordner) == [
        "HFS_Mueller-Luedenscheidt_Joerg_2026-11-03_100000.xlsx",
        "HFS_Mueller-Luedenscheidt_Joerg_2026-11-04_000001.xlsx",
    ]
    ws = load_workbook(ordner / dateien(ordner)[1])["Fragebogen"]
    werte = [c.value for r in ws.iter_rows() for c in r if c.value]
    assert "Korrektur der Abgabe vom 03.11.2026" in werte
    assert "vorherige Datei: HFS_Mueller-Luedenscheidt_Joerg_2026-11-03_100000.xlsx" in werte
    assert "Armbruch rechts und Prellung" in werte

    # danach wieder Fall B mit den neuen Antworten
    st = client.get(f"/api/status/{ID}").json()
    assert st["fall"] == "B" and st["antwort"]["gehindert_grund"] == "Armbruch rechts und Prellung"


def test_kanzlei_loescht_datei_dann_leerer_fragebogen(client, uhr, ordner):
    client.post("/api/antwort", json=beispiel())
    for p in ordner.glob("*.xlsx"):
        p.unlink()
    # sogar am selben Tag: Datei gelöscht -> neu beantworten möglich
    assert client.get(f"/api/status/{ID}").json() == {"fall": "A"}
    r = client.post("/api/antwort", json=beispiel())
    assert r.status_code == 201 and r.json()["korrektur"] is False


def test_nur_letzte_datei_geloescht_zeigt_vorherige_abgabe(client, uhr, ordner):
    client.post("/api/antwort", json=beispiel(gehindert_grund="erste"))
    uhr.stelle(2026, 11, 5, 9, 0, 0)
    client.post("/api/antwort", json=beispiel(gehindert_grund="zweite"))
    (ordner / "HFS_Mueller-Luedenscheidt_Joerg_2026-11-05_090000.xlsx").unlink()
    st = client.get(f"/api/status/{ID}").json()
    assert st["fall"] == "C" and st["antwort"]["gehindert_grund"] == "erste"


def test_geraete_sind_unabhaengig(client, uhr, ordner):
    assert client.post("/api/antwort", json=beispiel()).status_code == 201
    assert client.post("/api/antwort", json=beispiel(installations_id="anderes-geraet")).status_code == 201
    assert client.get("/api/status/anderes-geraet").json()["fall"] == "B"
    assert client.get("/api/status/drittes-geraet").json() == {"fall": "A"}


def test_ungueltige_kennung(client):
    assert client.get("/api/status/kurz").status_code == 400
    assert client.get("/api/status/..%2F..%2Fetc").status_code in (400, 404)


def test_validierung_ueber_api(client, ordner):
    assert client.post("/api/antwort", json=beispiel(einwilligung=False)).status_code == 422
    assert client.post("/api/antwort", json=beispiel(nachname="")).status_code == 422
    assert dateien(ordner) == []


def test_seiten_und_sicherheitsheader(client):
    r = client.get("/")
    assert r.status_code == 200 and "Haushaltsführungsschaden" in r.text
    assert r.headers["content-security-policy"].startswith("default-src 'self'")
    assert client.get("/datenschutz.html").status_code == 200
    assert client.get("/api/fragebogen").json()["max_staffeln"] == 4
    assert client.get("/docs").status_code == 404
