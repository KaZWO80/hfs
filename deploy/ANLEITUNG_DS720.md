# Installation auf der Synology DS720+ (Prototyp)

Diese Anleitung installiert den Fragebogen als Container auf der DS720+. Danach ist er **im eigenen WLAN/LAN** erreichbar:

- unverschlüsselt unter `http://<IP-des-NAS>:8080` (Teil 4)
- **verschlüsselt** unter `https://<IP-des-NAS>:8443` über den Reverse Proxy von DSM (Teil 4b, empfohlen)

> **Wichtig für den Prototyp:** keine Portfreigabe im Router einrichten und nur Testdaten eingeben. Der Echtbetrieb mit HTTPS folgt später (Plan, Schritt 7).

Zeitaufwand: ca. 20–30 Minuten. Die Menünamen beziehen sich auf DSM 7.2 und können je nach Version leicht abweichen.

---

## Teil 1 – Ordner auf dem NAS anlegen

1. **Systemsteuerung → Freigegebener Ordner → Erstellen**
   - Name: `hfs`
   - „Papierkorb aktivieren“: **ja**. Gelöschte Excel-Dateien lassen sich so wiederherstellen.
   - Verschlüsselung: für den Prototyp nicht nötig. Für den Echtbetrieb ist sie vorgesehen.
   - Berechtigungen: dein Benutzer **Lesen/Schreiben**, andere Benutzer **kein Zugriff**.
2. **File Station** öffnen, in `hfs` drei Unterordner anlegen:

   ```
   hfs/
   ├── app/          ← Programm
   ├── daten/        ← interne Daten (gespeicherte Antworten) – nicht bearbeiten
   └── ergebnisse/   ← hier erscheinen die Excel-Dateien
   ```

## Teil 2 – Programmdateien hochladen

1. Auf dem PC im Browser das Repository öffnen: **github.com/KaZWO80/hfs**
2. Oben links den Branch **`claude/fragebogen-app-android-ios-yrjlmu`** auswählen.
3. **Code → Download ZIP**, dann die ZIP-Datei auf dem PC entpacken.
4. In **File Station** den Ordner `hfs/app` öffnen und die beiden Ordner **`server`** und **`deploy`** aus dem entpackten Ordner hineinziehen (Drag & Drop).

   Danach sieht es so aus:

   ```
   hfs/app/
   ├── deploy/   (docker-compose.yml, Dockerfile, diese Anleitung)
   └── server/   (Programm, Formular, Excel-Vorlage)
   ```

## Teil 3 – Projekt im Container Manager anlegen

1. **Container Manager → Projekt → Erstellen**
2. Ausfüllen:
   - **Projektname:** `hfs-fragebogen`
   - **Pfad:** `/hfs/app/deploy` (über „Festlegen“ auswählen)
   - **Quelle:** Die Frage, ob die vorhandene `docker-compose.yml` verwendet werden soll, mit **Ja / Vorhandene verwenden** beantworten.
3. **Weiter.** Die „Web Station“- bzw. Webportal-Einstellungen **nicht** aktivieren.
4. **Fertig.** Den Haken „Projekt nach der Erstellung starten“ gesetzt lassen.
5. Der Container wird jetzt gebaut. Das dauert beim ersten Mal **2–5 Minuten**, die NAS lädt dabei Python und die Programmbibliotheken aus dem Internet. Fertig ist es, wenn unter **Container** der Eintrag `hfs-fragebogen` mit grünem Status „Wird ausgeführt“ erscheint.

## Teil 4 – Aufrufen und testen

1. **IP-Adresse des NAS** herausfinden: **Systemsteuerung → Netzwerk → Netzwerkschnittstelle** (z. B. `192.168.188.100`).
2. Am Handy, Tablet oder PC **im selben WLAN** im Browser eingeben:
   **`http://192.168.188.100:8080`** (mit deiner IP)

   > Das **`http://` unbedingt mit eintippen.** Ohne Angabe versuchen Chrome und Edge automatisch `https://`, was an Port 8080 mit **`ERR_SSL_PROTOCOL_ERROR`** scheitert. Kommt der Fehler trotzdem, die automatische Umstellung ausschalten:
   > - **Chrome:** Einstellungen → Datenschutz und Sicherheit → Sicherheit → „Immer sichere Verbindungen verwenden“ aus
   > - **Edge:** Einstellungen → Datenschutz, Suche und Dienste → Sicherheit → „Automatisch zu sichereren Verbindungen wechseln“ aus
   >
   > Einfacher ist es, gleich die verschlüsselte Adresse aus **Teil 4b** zu verwenden.
3. Tipp: Die Seite am Handy zum Startbildschirm hinzufügen, dann sieht sie aus wie eine App.
   - iPhone: Teilen → „Zum Home-Bildschirm“
   - Android: Menü ⋮ → „Zum Startbildschirm hinzufügen“

**Seite lädt nicht?**
- Prüfe unter **Systemsteuerung → Sicherheit → Firewall**, ob die Firewall aktiv ist. Wenn ja, eine Regel hinzufügen: Port **8080/TCP** erlauben, Quelle: dein Heimnetz (z. B. `192.168.188.0/24`).

## Teil 4b – Verschlüsselte Verbindung (HTTPS) einrichten

DSM nimmt die verschlüsselte Verbindung auf Port **8443** entgegen und leitet sie intern an den Container weiter. Am Container und an `docker-compose.yml` ändert sich nichts.

### 1. Reverse-Proxy-Regel anlegen

**Systemsteuerung → Anmeldeportal → Erweitert → Reverse Proxy → Erstellen**

| Feld | Eintrag |
|---|---|
| Beschreibung des Reverse Proxy | `hfs-fragebogen` |
| **Quelle** – Protokoll | `HTTPS` |
| Quelle – Hostname | `*` |
| Quelle – Port | `8443` |
| HSTS aktivieren | **nein** (sonst lässt sich die Zertifikatswarnung nicht bestätigen) |
| **Ziel** – Protokoll | `HTTP` |
| Ziel – Hostname | `localhost` |
| Ziel – Port | `8080` |

Mit **Speichern** bestätigen. Der Reiter „Benutzerdefinierte Kopfzeile“ wird nicht benötigt.

### 2. Zertifikat prüfen

**Systemsteuerung → Sicherheit → Zertifikat → Einstellungen**: In der Liste erscheint der Dienst `hfs-fragebogen` (Port 8443). Als Zertifikat das **Standardzertifikat** (meist „synology“) auswählen und **OK**.

### 3. Firewall (nur wenn die DSM-Firewall aktiv ist)

**Systemsteuerung → Sicherheit → Firewall → Regeln bearbeiten**: Port **8443/TCP** für dein Heimnetz erlauben (z. B. Quelle `192.168.188.0/24`).

### 4. Aufrufen

**`https://192.168.188.100:8443`** (mit deiner NAS-IP)

Beim ersten Aufruf zeigt **jedes Gerät einmal eine Warnung** („Verbindung ist nicht privat“ bzw. „nicht sicher“). Das ist im Heimnetz normal: Das Zertifikat der NAS ist selbst ausgestellt und nicht von einer öffentlichen Stelle bestätigt. **Die Verbindung ist trotzdem verschlüsselt.** Bestätigen so:

| Gerät / Browser | Bestätigen |
|---|---|
| Chrome / Edge (PC, Android) | **Erweitert** → **Weiter zu 192.168.188.100 (unsicher)** |
| Safari (iPhone, iPad, Mac) | **Details einblenden** → **diese Website besuchen** → nochmals **Website besuchen** |
| Firefox | **Erweitert…** → **Risiko akzeptieren und fortfahren** |

Danach merkt sich der Browser die Ausnahme für diese Adresse.

> **Hinweis:** Die Ausnahme gilt pro Gerät und Browser. Für Mandanten im Echtbetrieb ist diese Warnung nicht zumutbar, dort folgt in Schritt 7 eine eigene Internetadresse mit offiziellem Let's-Encrypt-Zertifikat, dann ohne Warnung.

**Optional:** Soll der Fragebogen **nur noch verschlüsselt** erreichbar sein, in `deploy/docker-compose.yml` die Zeile `- "8080:8080"` in `- "127.0.0.1:8080:8080"` ändern und das Projekt neu erstellen (Teil 6). Dann ist Port 8080 von außen gesperrt und nur der Reverse Proxy erreicht den Container. Eine Firewall-Regel für 8080 ist dann nicht mehr nötig.

## Teil 5 – Ergebnisse ansehen und verwalten

- Jede Abgabe erzeugt eine Datei in **`hfs/ergebnisse`**, z. B. `HFS_Mustermann_Max_2026-11-03_143000.xlsx`.
- Öffnen: per File Station herunterladen, über die Netzwerkfreigabe `\\<NAS-IP>\hfs\ergebnisse` am PC, oder per **Synology Drive** auf den PC synchronisieren (Drive-Client → Synchronisierungsaufgabe → Ordner `hfs/ergebnisse`).
- **Neu beantworten lassen:** Die Excel-Datei(en) dieser Person in `hfs/ergebnisse` **löschen**. Beim nächsten Aufruf bekommt die Person auf ihrem Gerät wieder einen leeren Fragebogen.
- Den Ordner **`hfs/daten` bitte nicht verändern.** Dort merkt sich das Programm, welches Gerät wann abgegeben hat.

## Teil 6 – Update einspielen (wenn es eine neue Version gibt)

1. **Container Manager → Projekt → hfs-fragebogen → Aktion → Stoppen**
2. In File Station die Ordner `hfs/app/server` und `hfs/app/deploy` durch die neuen Versionen ersetzen. Die Ordner `daten` und `ergebnisse` bleiben unverändert.
3. **Aktion → Erstellen** (baut den Container neu), danach **Starten**.

## Fehlersuche

| Problem | Lösung |
|---|---|
| `ERR_SSL_PROTOCOL_ERROR` / „keine sichere Verbindung“ an Port 8080 | Der Browser versucht `https://` an Port 8080. Entweder `http://…:8080` eintippen (Teil 4) oder `https://…:8443` verwenden (Teil 4b). |
| An Port 8443 erscheint die DSM-Anmeldung oder „Seite nicht gefunden“ | Reverse-Proxy-Regel prüfen: Ziel muss `HTTP` / `localhost` / `8080` sein, Quelle `HTTPS` / `8443`. |
| Zertifikatswarnung lässt sich nicht wegklicken | In der Reverse-Proxy-Regel **HSTS ausschalten**, Browserverlauf für die Adresse löschen, erneut aufrufen. |
| Projekt lässt sich nicht erstellen, Port 8080 belegt | In `deploy/docker-compose.yml` die Zeile `"8080:8080"` z. B. in `"8090:8080"` ändern. Aufruf dann mit `:8090`. |
| „Der Fragebogen konnte nicht geladen werden“ | Container läuft nicht. Unter **Container → hfs-fragebogen → Details → Protokoll** nachsehen. |
| Excel-Datei lässt sich nicht löschen | **Systemsteuerung → Freigegebener Ordner → hfs → Bearbeiten → Berechtigungen** prüfen, ob dein Benutzer Lesen/Schreiben hat. Notfalls als Administrator in File Station löschen. |
| Bau schlägt fehl („pip“, „Download“) | Die NAS braucht beim Bauen Internetzugang. Später erneut über **Aktion → Erstellen** versuchen. |
| Uhrzeit im Dateinamen stimmt nicht | Der Container verwendet deutsche Zeit. Unter **Systemsteuerung → Regionale Optionen** die NAS-Uhrzeit prüfen (Zeitserver aktivieren). |

---

## Test-Checkliste für Schritt 5

Bitte auf **Handy, Tablet und PC** durchgehen und Auffälligkeiten notieren:

- [ ] `https://<NAS-IP>:8443` öffnet sich nach einmaligem Bestätigen der Zertifikatswarnung
- [ ] Seite öffnet sich, alle Abschnitte 1–6 sind gut lesbar und bedienbar
- [ ] Datumsfelder zeigen das deutsche Format (TT.MM.JJJJ)
- [ ] Kommazahlen (z. B. „1,5“ Std./Woche) lassen sich eingeben
- [ ] Zeiträume hinzufügen und entfernen funktioniert
- [ ] Seite schließen und wieder öffnen: Eingaben sind noch da
- [ ] Absenden ohne Einwilligung → Hinweis erscheint
- [ ] Absenden → „Vielen Dank“, Datei erscheint in `hfs/ergebnisse` mit richtigem Namen
- [ ] Excel-Datei öffnen: Blatt „Fragebogen“ vollständig, Blatt „HFS“ richtig vorbefüllt, Formeln rechnen nach Eintragen von Stundensatz und Stunden/Tag
- [ ] Seite am selben Tag erneut öffnen → „bereits abgegeben“, nur Lesen
- [ ] **Am nächsten Tag** erneut öffnen → Angaben vorausgefüllt, Korrektur absenden → zweite Datei mit Vermerk „Korrektur der Abgabe vom …“
- [ ] Datei(en) in `hfs/ergebnisse` löschen → Seite neu laden → leerer Fragebogen
- [ ] Zweites Gerät: eigener, unabhängiger Fragebogen
