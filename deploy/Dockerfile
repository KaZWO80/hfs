# Container für den Fragebogen Haushaltsführungsschaden.
# Wird von docker-compose.yml gebaut (Build-Kontext = Ordner über deploy/).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin \
    HFS_DATEN_ORDNER=/daten \
    HFS_ERGEBNIS_ORDNER=/ergebnisse

WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/app.py server/excel_export.py server/models.py server/questionnaire.py ./
COPY server/static ./static
COPY server/templates ./templates

EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/fragebogen', timeout=4)"

# Genau ein Prozess (--workers 1): die Tagessperre setzt eine gemeinsame Sperre im Speicher voraus.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-server-header"]
