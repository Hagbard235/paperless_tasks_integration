# paperless_tasks_integration
Ein Tool das beim erstellen/ändern von paperless-Dokumenten einen Eintrag bei Google Tasks macht undn einen Bearbeitugnsstatus integriert

## Konfiguration

Die Anwendung liest ihre Einstellungen aus `config.json`. Neu hinzugekommen ist
`SERVER_BASE_URL`, unter der der Flask-Server von extern erreichbar ist. Diese
Adresse wird zum Aufbau der Links für den Statusdialog und den PDF-Viewer
verwendet.

Im Konfigurationsdialog werden die Google-Parameter (Client-ID, Secret,
Token-Datei und Scopes) nicht mehr angezeigt, da diese üblicherweise nicht von
Hand geändert werden.
