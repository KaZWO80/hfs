# Plan: Web-App „Fragebogen Haushaltsführungsschaden“

Stand: 03.11.2026 · Status: **fertig, wartet auf Freigabe** – es wird erst gebaut, wenn dieser Plan freigegeben ist.

---

## 1. Ziel

Mandantinnen und Mandanten füllen den Fragebogen zum Haushaltsführungsschaden am Handy, Tablet oder PC im Browser aus.
Nach dem Absenden entsteht auf dem NAS automatisch **eine Excel-Datei pro Fragebogen**:

- Grundlage ist die Vorlage **Anspruchsberechnungen.xlsx** mit allen Blättern und Formeln.
- Ein zusätzliches Blatt **„Fragebogen“** enthält **alle Fragen samt Antworten**.
- Das Blatt **„HFS“** wird mit den Angaben vorbefüllt.
- Der Dateiname enthält **Nachname und Vorname**.
- **Pro Gerät/Browser höchstens eine Abgabe pro Tag.** Bereits abgegebene Antworten werden angezeigt, Korrekturen ab dem Folgetag kommen in eine neue Datei (Abschnitt 6).

## 2. Rahmenbedingungen (festgelegt)

| Punkt | Entscheidung |
|---|---|
| Plattform | Web-App im Browser (keine App-Store-App) |
| Server | Synology **DS720+**, DSM 7.2, **Container Manager** (Docker) – „Weg 2“ |
| Excel-Inhalt | Kopie der Vorlage + Blatt „Fragebogen“ mit allen Fragen und Antworten |
| Prototyp-Zugriff | zunächst nur im eigenen Netzwerk (WLAN/LAN) |

## 3. Architektur

```
 Handy / Tablet / PC (Browser)
          │  Formular ausfüllen, Entwurf bleibt im Browser gespeichert
          │  POST /api/antwort  (JSON)
          ▼
 DS720+ ─ Container Manager ─ Container „hfs-fragebogen“
          │  Python (FastAPI) + openpyxl
          │  1. Angaben prüfen
          │  2. Prüfen: wurde auf diesem Gerät schon abgegeben?
          │  3. Vorlage kopieren, Blätter befüllen, speichern
          ▼
 NAS-Ordner  /volume1/hfs/ergebnisse/HFS_Nachname_Vorname_2026-11-03_140509.xlsx
          │  (optional per Synology Drive auf den Kanzlei-PC synchronisiert)
```

- **Frontend:** eine Seite mit HTML, CSS und JavaScript, ohne App-Installation. Optimiert für Smartphones, funktioniert auch auf Tablet und PC.
- **Backend:** ein kleiner Python-Dienst in einem Docker-Container.
- **Ablage:** ein normaler freigegebener Ordner auf dem NAS. Die Dateien lassen sich direkt mit Excel öffnen. Eine eigene Admin-Seite ist für den Prototyp nicht nötig.

## 4. Inhalt des Fragebogens

Inhalt 1:1 aus *Haushaltsführungsschaden_Fragebogen.docx*, ergänzt um die Personenangaben:

1. **Person:** Anrede (Frau/Herr – steht in der Kopfzeile des Word-Fragebogens), **Vorname\***, **Nachname\***
2. **Haushaltsführung und Beeinträchtigung**
   - Aufteilung vor dem Unfall: Ich % / Andere %
   - Zeitraum der unfallbedingten Verhinderung (von–bis)
   - Warum konkret gehindert? (Freitext)
   - Grad der Beeinträchtigung in %, **gestaffelt bis zu 4 Zeiträume** (von–bis–%)
   - Schmerzen bei alltäglichen Bewegungen/Tätigkeiten (Freitext)
3. **Haushalt und Wohnsituation**
   - Personen im Haushalt, Alter der Kinder
   - Haus/Wohnung, Eigentum/Miete
   - qm, Räume, Etagen, Besonderheiten
   - Garten ja (qm)/nein
   - Haushaltsgeräte (11 Ankreuzfelder + Sonstiges)
   - Haushaltshilfe generell ja/nein
   - Bezahlte Haushaltshilfe während der Einschränkungen: ja (von–bis, Tätigkeiten)/nein, mit Hinweis auf Belege
4. **Tätigkeiten vor dem Unfall:** 23 Tätigkeiten, jeweils Ankreuzen + wöchentlicher Zeitaufwand in Std.; Zusatzfeld bei Gartenpflege (konkret), Kinderbetreuung (von), Betreuung Angehöriger (von), Haustier (Art), Sonstiges. Die Wochensumme wird live angezeigt.
5. **Beeinträchtigung nach dem Unfall:** dieselben 23 Tätigkeiten, jeweils Ankreuzen + „wieder möglich ab“ (Datum)
6. **Absenden:** Einwilligung zur Datenverarbeitung (Pflicht, inkl. Gesundheitsdaten) + Link zur Datenschutzerklärung

Pflichtfelder sind nur Vorname, Nachname und die Einwilligung. Alle anderen Fragen sind freiwillig, so wie im Papierbogen.

## 5. Aufbau der Excel-Datei

### 5.1 Dateiname
`HFS_<Nachname>_<Vorname>_<JJJJ-MM-TT>_<hhmmss>.xlsx`

- Umlaute werden umgeschrieben (ä→ae, ö→oe, ü→ue, ß→ss), Sonderzeichen und Leerzeichen werden zu „-“.
  Beispiel: *Jörg Müller-Lüdenscheidt* → `HFS_Mueller-Luedenscheidt_Joerg_2026-11-03_140509.xlsx`
- Datum und Uhrzeit im Namen sorgen dafür, dass bei gleichen Namen keine Datei überschrieben wird.

### 5.2 Blatt „Fragebogen“ (neu, wird beim Öffnen als erstes angezeigt)
Drei Spalten: **Frage | Antwort | Ergänzung/Freitext**, gegliedert nach den Abschnitten 1–6.
Alle Fragen werden aufgeführt, **auch unbeantwortete** (Antwort leer). Die Tätigkeitslisten erscheinen als Tabellen (Tätigkeit | Std./Woche | Angaben bzw. Tätigkeit | wieder möglich ab).

### 5.3 Blatt „HFS“ (vorhanden, wird vorbefüllt)

| Zelle(n) | Inhalt | Quelle |
|---|---|---|
| A2–A5 | Zeitraum „TT.MM.JJJJ – TT.MM.JJJJ“ | Staffeln aus Frage 2 |
| B2–B5 „Tage“ | Anzahl Tage je Staffel (inkl. Start- und Endtag) | berechnet |
| C2–C5 „Anteil in %“ | Grad der Beeinträchtigung (z. B. 50 % → 0,5) | Staffeln |
| D2–D5 „Stundensatz“ | **bleibt leer**, wird in der Kanzlei eingetragen (Entscheidung 2) | – |
| E2–E5 „Stunden/Tag“ | **bleibt leer**, wird in der Kanzlei eingetragen (Entscheidung 1) | – |
| F2–F6 | Formeln der Vorlage bleiben unverändert | Vorlage |
| B10–B34 „Wöch Aufw“ | Wochenstunden je Tätigkeit | Abschnitt 4 |

Zuordnung der Tätigkeiten (Fragebogen → HFS-Zeile):

| Fragebogen | Zeile | Fragebogen | Zeile |
|---|---|---|---|
| Staubsaugen | 10 | Wäsche waschen und aufhängen | 21 ¹ |
| Boden wischen | 11 | Wäsche bügeln | 23 |
| Fenster putzen | 12 | Betten machen | 24 |
| Staub wischen | 13 | Einkaufen | 25 |
| Bad putzen | 14 | Müll entsorgen | 26 |
| Bad feucht reinigen | 15 („Sanitär feucht reinigen“) | Autopflege | 27 |
| Aufräumen | 16 | Gartenpflege | 28 |
| Geschirr abwaschen | 17 | Kinderbetreuung | 29 |
| Geschirr abtrocknen | 18 | Betreuung naher Angehöriger | 30 |
| Geschirr einräumen | 19 | Korrespondenz | 31 |
| Kochen | 20 | Versorgung Haustier | 32 |
| – | 33 „Reparaturarbeiten“ ² | Sonstiges | 34 |

¹ Excel trennt „Wäsche waschen“ (21) und „Wäsche aufhängen“ (22). Der Fragebogen bleibt wie er ist (Entscheidung 3): Der Wert kommt in Zeile 21, Zeile 22 bleibt leer.
² „Reparaturarbeiten“ wird nicht in den Fragebogen aufgenommen (Entscheidung 3). Zeile 33 bleibt leer.

Excel berechnet beim Öffnen alle Formeln neu. Damit stimmen auch die Werte in **P-Sch** (HFS!F6 → P-Sch!B4) und **S-Sch** sofort.

## 6. Abgabe, Anzeige und Korrektur (Sperre pro Tag)

**Grundidee:** Pro Gerät/Browser ist **eine Abgabe pro Kalendertag** möglich (deutsche Zeit, Tageswechsel um 0:00 Uhr). Korrekturen sind ab dem nächsten Tag möglich und landen in einer **neuen** Datei. Die alte Datei bleibt erhalten.

**Technik:** Beim ersten Aufruf erzeugt der Browser eine zufällige Kennung (keine persönlichen Daten) und speichert sie. Der Server speichert zu jeder Kennung die abgegebenen Antworten (intern als JSON-Datei im Ordner `hfs/daten`, nicht im Ergebnisordner) und den Namen der zugehörigen Excel-Datei.

Beim Öffnen der Seite gibt es drei Fälle:

| Fall | Situation | Was die Mandantin/der Mandant sieht |
|---|---|---|
| A | Noch nie abgegeben **oder** die Kanzlei hat alle Excel-Dateien dieser Abgabe gelöscht | **Leerer Fragebogen**, normale Abgabe |
| B | **Heute** schon abgegeben | Die eigenen **Antworten nur zum Lesen** und der Hinweis „Änderungen sind ab morgen möglich.“ Kein Absenden möglich. |
| C | An einem **früheren Tag** abgegeben, Datei ist noch vorhanden | Fragebogen **mit den letzten Antworten vorausgefüllt**, änderbar. Das Absenden erzeugt eine **neue Excel-Datei** mit dem Datum des neuen Tages. Danach gilt wieder Fall B. |

**Neu beantworten (leerer Fragebogen):** Das geht nur, wenn die Kanzlei vorher die Excel-Datei(en) dieser Person im Ordner `hfs/ergebnisse` **löscht**. Der Server erkennt das beim nächsten Aufruf, verwirft die gespeicherten Antworten und zeigt Fall A.

**Kennzeichnung von Korrekturen:** Das Blatt „Fragebogen“ einer Korrektur enthält die Zeile „Korrektur der Abgabe vom TT.MM.JJJJ (Datei …)“. Der Dateiname folgt demselben Muster wie in 5.1, das neue Datum unterscheidet ihn.

**Grenze (bewusst akzeptiert):** Ein anderer Browser, der Privatmodus oder gelöschte Browserdaten gelten als neues Gerät. Dort beginnt man mit einem leeren Fragebogen, die bisherigen Antworten werden dort nicht angezeigt.

## 7. Sicherheit und Datenschutz

**Prototyp (nur im Heimnetz):**
- Aufruf über `http://<NAS-IP>:8080` oder verschlüsselt über `https://<NAS-IP>:8443` (DSM-Reverse-Proxy mit NAS-eigenem Zertifikat, einmalige Browser-Warnung; Anleitung Teil 4b). Ohne Router-Freigabe, also nicht aus dem Internet erreichbar.
- Testen von unterwegs nur über **Tailscale** (Synology-Paket), nicht über offene Ports.
- Nur Testdaten eingeben, keine echten Mandantendaten.

**Echtbetrieb (spätere Phase, eigene Freigabe):**
- **HTTPS** mit Let's-Encrypt-Zertifikat, DDNS-Adresse und DSM-Reverse-Proxy. Port 443 wird nur für diesen Dienst freigegeben.
- DSM aktuell halten, 2-Faktor-Anmeldung für DSM, Firewall/Geo-Blocking, automatische Sperre bei Fehlversuchen.
- Ergebnisordner in einem **verschlüsselten freigegebenen Ordner**, Zugriff nur für die Kanzlei, regelmäßige Sicherung (Hyper Backup).
- Den Container nur mit den nötigen Rechten betreiben. Er sieht nur seinen eigenen Ordner.
- DSGVO: Datenschutzerklärung, Einwilligung (Art. 9 DSGVO, Gesundheitsdaten), Löschfristen, Verzeichnis der Verarbeitungstätigkeiten.
- **Alternative prüfen:** ein Server in einem deutschen Rechenzentrum statt des NAS im Büro.

## 8. Umsetzung in Schritten (mit Freigabe nach jedem Schritt)

| Schritt | Inhalt | Ergebnis zum Prüfen |
|---|---|---|
| 1 | Plan freigeben (alle Fragen entschieden) | dieser Plan |
| 2 | Excel-Erzeugung bauen + automatische Tests | **Beispiel-Excel mit Testdaten** zum Ansehen |
| 3 | Formular (Frontend) bauen | Screenshots Handy/PC |
| 4 | Docker-Paket + Installationsanleitung für die DS720+ | Anleitung Schritt für Schritt |
| 5 | Du installierst auf der DS720+ und testest auf Handy, Tablet, PC | Feedback-Liste |
| 6 | Korrekturen | – |
| 7 | (später) Echtbetrieb: HTTPS, Datenschutz, Härtung | eigene Freigabe |

## 9. Installation auf der DS720+ (Vorschau für Schritt 4)

1. In **File Station** den Ordner `hfs` anlegen, darin `app`, `daten` und `ergebnisse`.
2. Projektdateien aus dem Repository nach `hfs/app` kopieren.
3. **Container Manager → Projekt → Erstellen**: Pfad `hfs/app`, vorhandene `docker-compose.yml` verwenden, starten.
4. Am Handy im WLAN `http://<NAS-IP>:8080` öffnen und testen.
5. Ergebnisse erscheinen in `hfs/ergebnisse`. Optional diesen Ordner per Synology Drive auf den PC synchronisieren.

## 10. Geplante Ordnerstruktur im Repository

```
plan/        dieser Plan, Excel-Vorlage (Anspruchsberechnungen.xlsx), Word-Fragebogen
server/      Python-Dienst (FastAPI), Excel-Erzeugung, Tests
server/static/     Formular (HTML/CSS/JS)
server/templates/  Kopie der Excel-Vorlage aus plan/ (wird in Schritt 2 angelegt)
deploy/      Dockerfile, docker-compose.yml, Anleitung DS720+
```

## 11. Entscheidungen (03.11.2026)

1. **Stunden/Tag (HFS Spalte E):** wird **nicht** vorbefüllt, bleibt leer.
2. **Stundensatz (Spalte D):** bleibt leer.
3. **Tätigkeitsliste:** bleibt wie im Word-Fragebogen. Wäsche waschen und aufhängen stehen zusammen in Zeile 21, „Reparaturarbeiten“ kommt nicht hinzu.
4. **Repository:** Excel-Vorlage und Word-Fragebogen liegen im Ordner `plan/`. Die Luckey-PDF wird nicht hochgeladen.
5. **Keine zusätzlichen Fragen** aus der Luckey-Checkliste.
6. **Datenschutz:** zunächst Platzhaltertexte für Datenschutzerklärung und Einwilligung, gekennzeichnet mit `[PLATZHALTER]`. Diese müssen vor dem Echtbetrieb ersetzt werden.
7. **Sperre pro Tag** mit Anzeige und Korrektur, siehe Abschnitt 6.
8. **Umsetzung:** Der bisherige Code-Entwurf dient als technische Ausgangsbasis und wird an diesen Plan angepasst, zum Beispiel ohne Vorbefüllung von Spalte E und mit der Tagessperre.
