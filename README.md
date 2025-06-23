# paperless_tasks_integration

Dieses Projekt stellt einen kleinen Flask-Server bereit, der eine Paperless-Installation mit Google Tasks verbindet. Beim Erstellen oder Ändern eines Paperless-Dokuments wird automatisch eine Aufgabe in Google Tasks angelegt. Zudem lässt sich der Bearbeitungsstatus direkt über den Server setzen und mit Google synchronisieren.

## Installation
1. Python 3 muss installiert sein.
2. Repository klonen oder als ZIP herunterladen und entpacken.
3. Abhängigkeiten installieren:
   ```bash
   pip install flask requests google-api-python-client google-auth
   ```
4. Die Datei `config.example.json` nach `config.json` kopieren und anpassen.
   Dort werden alle benötigten Tokens und IDs hinterlegt.

## Konfiguration
Die Anwendung liest ihre Einstellungen aus `config.json`. Wichtige Parameter sind unter anderem:

- `PAPERLESS_URL` und `PAPERLESS_TOKEN`: Zugriffsdaten für die Paperless-API
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_TASKS_TOKEN`: Zugangsdaten für Google Tasks
- `ACTION_TASK_LIST_ID`: Die Liste, in der neue Aufgaben angelegt werden
- `CUSTOM_FIELD_STATUS`, `CUSTOM_FIELD_AKTION`, `CUSTOM_FIELD_BEARBEITET`: IDs der Custom Fields in Paperless
- `STATUS_LABEL_NEW` und `STATUS_LABEL_DONE`: Bezeichnungen der Bearbeitungszustände
- `SERVER_BASE_URL`, `SERVER_HOST`, `SERVER_PORT`: URL und Port des Servers

Die Datei `config.example.json` enthält Beispielwerte und dient als Vorlage. Optional kann die Pfadangabe über die Umgebungsvariable `CONFIG_PATH` geändert werden.

## Starten der Anwendung
Nach dem Anpassen der Konfiguration kann der Server einfach mit

```bash
python3 paperless_task_integration.py
```

oder mit einer angepassten Konfigurationsdatei gestartet werden:

```bash
CONFIG_PATH=/pfad/zur/config.json python3 paperless_task_integration.py
```

Der Server lauscht standardmäßig unter `http://<SERVER_HOST>:<SERVER_PORT>/` und stellt folgende Endpunkte bereit:

- `/paperless_webhook` – Webhook zum Empfangen von Paperless-Ereignissen
- `/status/<doc_id>` – Oberfläche zum Ändern des Bearbeitungsstatus
- `/view_pdf/<doc_id>` und `/proxy_download/<doc_id>` – Anzeige bzw. Download der PDF-Datei
- `/config` – einfache Weboberfläche zur Bearbeitung der Konfiguration

## Funktionsweise
1. Paperless sendet per Webhook Informationen zu neu erstellten oder geänderten Dokumenten an `/paperless_webhook`.
2. Der Server legt daraufhin eine Aufgabe in Google Tasks an, sofern das Dokument laut KI bearbeitet werden soll.
3. Über die Statusseite kann der Bearbeitungsstatus geändert werden. Diese Änderung wird in Paperless gespeichert und in der verknüpften Google-Task-Notiz vermerkt.
4. Ein Hintergrundjob prüft regelmäßig erledigte Aufgaben in Google Tasks und markiert die zugehörigen Paperless-Dokumente als erledigt.

## Weitere Hinweise
- Für den Zugriff auf Google Tasks ist eine vorherige Authentifizierung notwendig. Das Token wird in der in `GOOGLE_TASKS_TOKEN` angegebenen Datei gespeichert.
- Die Google-Parameter (Client-ID, Secret, Token-Datei und Scopes) werden in der Konfigurationsoberfläche ausgeblendet, da sie in der Regel nicht häufig geändert werden.
- Die Anwendung eignet sich sowohl für lokale Tests als auch für den Betrieb in einem privaten Netzwerk.

