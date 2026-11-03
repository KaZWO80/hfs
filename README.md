# Fragebogen Haushaltsführungsschaden

Web-App für Handy, Tablet und PC. Pro ausgefülltem Fragebogen entsteht eine Excel-Datei auf Basis der Vorlage *Anspruchsberechnungen.xlsx*. Der Name der Datei enthält Nachname und Vorname.

| Ordner | Inhalt |
|---|---|
| [`plan/`](plan/PLAN.md) | Plan, Entscheidungen, Excel-Vorlage, Word-Fragebogen |
| `server/` | Programm (Python/FastAPI), Formular (`static/`), Excel-Erzeugung, Tests |
| `deploy/` | Docker-Paket und [Installationsanleitung für die DS720+](deploy/ANLEITUNG_DS720.md) |
| `beispiele/` | Beispiel-Excel mit Testdaten |

## Entwicklung

```bash
cd server
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest            # automatische Tests
uvicorn app:app --port 8080 # http://localhost:8080
```
